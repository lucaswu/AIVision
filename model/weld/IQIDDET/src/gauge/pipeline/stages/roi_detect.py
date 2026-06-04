#!/usr/bin/env python3
"""Pipeline stage: detect IQI ROI via YOLO-OBB, crop, and preprocess."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

from gauge.domain.record_builders import build_skipped_ocr
from gauge.imaging.geometry import invert_perspective_matrix, scale_roi_info_to_original
from gauge.imaging.preprocess import (
    crop_rotated_polygon,
    enhance_windowing_gray,
    rotate_if_wide,
    to_gray,
)
from gauge.services.roi.yolo_obb import extract_best_obb
from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class ROIDetectStage(PipelineStage):
    """Detect the IQI ROI using YOLO-OBB, then crop, rotate, and enhance."""

    name = "roi_detect"

    def run(self, ctx: StageContext) -> StageContext:
        logger.debug("stage_started", extra={"stage": self.name, "image": ctx.image_path})
        gauge_model = self.services.get("gauge_model")
        config = self.config.gauge

        yolo_result = gauge_model.predict(
            source=ctx.sampled_image,
            conf=config.conf,
            iou=config.iou,
            imgsz=config.imgsz,
            device=config.device,
            verbose=False,
        )

        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["gauge_yolo_result"] = (
                yolo_result[0] if yolo_result else None
            )

        if not yolo_result:
            ctx.roi_info = None
            ctx.roi_ocr_result = build_skipped_ocr(
                "skipped_no_roi", "未检测到像质计 ROI"
            )
            logger.info("stage_done", extra={"stage": self.name, "roi_found": False, "reason": "no_detection"})
            return ctx

        roi_info_resized = extract_best_obb(
            yolo_result[0],
            select=config.select,
            class_filter=config.class_filter,
        )
        if roi_info_resized is None:
            ctx.roi_info = None
            ctx.roi_ocr_result = build_skipped_ocr(
                "skipped_no_roi", "未检测到像质计 ROI"
            )
            logger.info("stage_done", extra={"stage": self.name, "roi_found": False, "reason": "no_best_obb"})
            return ctx

        roi_info = scale_roi_info_to_original(
            roi_info_resized, ctx.resize_scale
        )
        polygon = np.array(roi_info["polygon"], dtype=np.float32)
        roi_cropped, crop_matrix = crop_rotated_polygon(ctx.image, polygon)

        if roi_cropped is None or crop_matrix is None:
            ctx.roi_info = None
            ctx.roi_ocr_result = build_skipped_ocr(
                "skipped_roi_invalid", "像质计 ROI 透视展开失败"
            )
            logger.info("stage_done", extra={"stage": self.name, "roi_found": False, "reason": "crop_failed"})
            return ctx

        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["roi_cropped"] = roi_cropped
            ctx.debug_artifacts["roi_crop_matrix"] = crop_matrix

        pre_rotate_size = [
            int(roi_cropped.shape[1]),
            int(roi_cropped.shape[0]),
        ]
        crop_inverse_matrix = invert_perspective_matrix(crop_matrix)
        roi_image, rotated, _rotation = rotate_if_wide(
            roi_cropped, enable=self.config.enhance.rotate_roi
        )

        if self.config.enhance.mode == "windowing":
            roi_gray = enhance_windowing_gray(roi_image)
        else:
            roi_gray = to_gray(roi_image)

        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["roi_image"] = roi_image
            ctx.debug_artifacts["roi_gray"] = roi_gray

        # Build record-style roi_info
        ctx.roi_info = {
            **roi_info,
            "crop_size_before_rotate": pre_rotate_size,
            "crop_inverse_matrix": crop_inverse_matrix.tolist(),
        }
        ctx.roi_cropped = roi_cropped
        ctx.roi_image = roi_image
        ctx.roi_gray = roi_gray
        ctx.roi_crop_matrix = crop_inverse_matrix
        ctx.pre_rotate_size = pre_rotate_size
        ctx.rotated = bool(rotated)

        logger.info("stage_done", extra={"stage": self.name, "roi_found": True, "rotated": bool(rotated)})
        return ctx
