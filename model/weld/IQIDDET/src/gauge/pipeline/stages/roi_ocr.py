#!/usr/bin/env python3
"""Pipeline stage: OCR on the IQI ROI and plate marker matching."""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import numpy as np

from gauge.domain.iqi_rules import infer_plate_from_ocr_items
from gauge.imaging.geometry import is_usable_ocr_item, project_ocr_items_to_image
from gauge.imaging.visualization import build_plate_visualization_items
from gauge.services.ocr.infer import infer_roi_ocr
from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class ROIOCRStage(PipelineStage):
    """Run OCR on the cropped and preprocessed ROI, then match plate markers."""

    name = "roi_ocr"

    def should_run(self, ctx) -> bool:
        return ctx.roi_gray is not None

    def run(self, ctx: StageContext) -> StageContext:
        logger.debug("stage_started", extra={"stage": self.name, "image": ctx.image_path})
        config = self.config
        ocr_backend = self.services.get("ocr_backend")
        ocr_text_corrector = self.services.get("ocr_text_corrector")

        # Run ROI OCR
        roi_ocr_result = infer_roi_ocr(
            ocr_backend,
            ocr_backend,
            ctx.roi_gray,
            min_score=config.ocr.min_score,
            text_orientation_corrector=ocr_text_corrector,
            text_orientation_verbose=config.ocr.orientation_verbose,
        )
        # Merge OCR timings with prefix
        if roi_ocr_result:
            for key, value in (roi_ocr_result.get("timings_ms") or {}).items():
                normalized_key = str(key)
                if normalized_key == "text_total_ms":
                    ctx.timings_ms["roi_ocr_ms"] = float(value)
                else:
                    ctx.timings_ms[f"roi_{normalized_key}"] = float(value)

        # Match plate markers
        roi_plate_result = infer_plate_from_ocr_items(
            roi_ocr_result.get("all_items") or [],
            require_jb=True,
            allowed_numbers=parse_allowed_numbers(config.ocr.number_range),
        )

        # Project items back to image coordinates
        crop_inverse_matrix = (
            np.array(
                ctx.roi_info.get("crop_inverse_matrix"), dtype=np.float32
            )
            if ctx.roi_info and ctx.roi_info.get("crop_inverse_matrix")
            else None
        )
        roi_projected_items = project_ocr_items_to_image(
            roi_ocr_result.get("all_items") or [],
            crop_inverse_matrix=crop_inverse_matrix,
            pre_rotate_size=ctx.pre_rotate_size,
            rotated=ctx.rotated,
        )
        roi_plate_vis_items = build_plate_visualization_items(
            roi_projected_items, source="roi"
        )

        roi_ocr_result = dict(roi_ocr_result)
        roi_ocr_result["all_items_image"] = roi_projected_items
        roi_ocr_result["items_image"] = [
            item
            for item in roi_projected_items
            if is_usable_ocr_item(item)
        ]

        if roi_plate_result is not None:
            roi_plate_result = dict(roi_plate_result)
            roi_plate_result["raw_text_items"] = roi_plate_vis_items

        warnings: List[str] = []
        if roi_ocr_result.get("item_errors"):
            warnings.append("ROI OCR存在部分文本框识别异常")
        if roi_plate_result and roi_plate_result.get("corrections"):
            warnings.append("ROI OCR 标识解析触发了规则纠错")
        ctx.warnings.extend(warnings)

        ctx.roi_ocr_result = roi_ocr_result
        ctx.roi_plate_result = roi_plate_result
        ctx.roi_plate_vis_items = roi_plate_vis_items

        logger.info(
            "stage_done",
            extra={
                "stage": self.name,
                "marker_found": bool(roi_plate_result and roi_plate_result.get("ok")),
            },
        )
        return ctx


def parse_allowed_numbers(spec: Optional[str]) -> Any:
    from gauge.domain.iqi_rules import parse_allowed_numbers_spec

    return parse_allowed_numbers_spec(spec)
