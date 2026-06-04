#!/usr/bin/env python3
"""Pipeline stage: full image OCR, general field extraction, and plate matching."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from gauge.domain.iqi_rules import (
    extract_general_fields_from_ocr_items,
    infer_plate_from_ocr_items,
)
from gauge.imaging.geometry import is_usable_ocr_item, scale_ocr_items_to_original
from gauge.imaging.preprocess import (
    enhance_windowing_gray,
    resize_long_side,
)
from gauge.imaging.visualization import build_plate_visualization_items
from gauge.services.ocr.infer import infer_roi_ocr
from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class FullImageOCRStage(PipelineStage):
    """Run OCR on the full image, extract general fields, and match IQI plate markers."""

    name = "full_image_ocr"

    def run(self, ctx: StageContext) -> StageContext:
        logger.debug("stage_started", extra={"stage": self.name, "image": ctx.image_path})
        config = self.config
        ocr_backend = self.services.get("ocr_backend")
        ocr_text_corrector = self.services.get("ocr_text_corrector")

        # Resize for OCR
        sampled_image, resize_scale = resize_long_side(
            ctx.image, config.ocr.det_limit_side_len
        )
        ctx.sampled_image = sampled_image
        ctx.resize_scale = float(resize_scale)

        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["sampled_image"] = sampled_image

        # Enhance for OCR
        full_ocr_input = enhance_windowing_gray(sampled_image)
        if ctx.debug_artifacts is not None:
            ctx.debug_artifacts["full_ocr_input"] = full_ocr_input

        # Run OCR
        full_ocr_result = infer_roi_ocr(
            ocr_backend,
            ocr_backend,
            full_ocr_input,
            min_score=config.ocr.min_score,
            text_orientation_corrector=ocr_text_corrector,
            text_orientation_verbose=config.ocr.orientation_verbose,
        )
        # Merge OCR timings with prefix
        if full_ocr_result:
            for key, value in (full_ocr_result.get("timings_ms") or {}).items():
                normalized_key = str(key)
                if normalized_key == "text_total_ms":
                    ctx.timings_ms["full_ocr_ms"] = float(value)
                else:
                    ctx.timings_ms[f"full_{normalized_key}"] = float(value)

        # Scale items back to original image coordinates
        full_items_original = scale_ocr_items_to_original(
            full_ocr_result.get("all_items") or [], resize_scale
        )
        full_plate_vis_items = build_plate_visualization_items(
            full_items_original, source="full_image"
        )
        full_ocr_result = dict(full_ocr_result)
        full_ocr_result["all_items_original"] = full_items_original
        full_ocr_result["items_original"] = [
            item for item in full_items_original if is_usable_ocr_item(item)
        ]

        # Extract general fields
        general_fields_data = extract_general_fields_from_ocr_items(
            full_items_original
        )

        # Match plate markers
        full_plate_result = infer_plate_from_ocr_items(
            full_items_original,
            require_jb=True,
            allowed_numbers=parse_allowed_numbers(config.ocr.number_range),
        )
        full_plate_result = dict(full_plate_result)
        full_plate_result["raw_text_items"] = full_plate_vis_items

        # Collect warnings
        warnings: list = []
        if full_ocr_result.get("item_errors"):
            warnings.append("全图OCR存在部分文本框识别异常")
        if full_plate_result.get("corrections"):
            warnings.append("全图 OCR 标识解析触发了规则纠错")
        ctx.warnings.extend(warnings)

        # Build field statistics
        field_statistics = dict(
            general_fields_data.get("field_statistics") or {}
        )
        field_statistics["full_image_marker_found"] = bool(
            full_plate_result.get("ok")
        )
        field_statistics["roi_marker_found"] = False
        field_statistics["iqi_marker_found"] = bool(
            full_plate_result.get("ok")
        )

        ctx.full_ocr_result = full_ocr_result
        ctx.full_plate_result = full_plate_result
        ctx.full_plate_vis_items = full_plate_vis_items
        ctx.general_fields_data = general_fields_data
        ctx.field_statistics = field_statistics

        logger.info(
            "stage_done",
            extra={
                "stage": self.name,
                "marker_found": bool(full_plate_result.get("ok")),
                "general_fields_found": field_statistics.get("general_fields_found", False),
            },
        )
        return ctx


def parse_allowed_numbers(spec: Optional[str]) -> Any:
    """Parse allowed numbers string to frozenset."""
    from gauge.domain.iqi_rules import parse_allowed_numbers_spec

    return parse_allowed_numbers_spec(spec)
