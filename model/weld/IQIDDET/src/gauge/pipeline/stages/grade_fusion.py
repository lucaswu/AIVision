#!/usr/bin/env python3
"""Pipeline stage: plate selection, grade computation, and error compilation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from gauge.domain.iqi_rules import (
    build_result_status,
    compute_iqi_grade,
    parse_allowed_numbers_spec,
)
from gauge.domain.record_builders import build_skipped_wire
from gauge.pipeline.context import StageContext
from gauge.pipeline.stages.base import PipelineStage

logger = logging.getLogger(__name__)


class GradeFusionStage(PipelineStage):
    """Select the best plate result, compute IQI grade, and compile errors."""

    name = "grade_fusion"

    def run(self, ctx: StageContext) -> StageContext:
        logger.debug("stage_started", extra={"stage": self.name, "image": ctx.image_path})
        config = self.config
        allowed_numbers = parse_allowed_numbers_spec(config.ocr.number_range)
        roi_error_code: Optional[int] = None
        roi_error_message: Optional[str] = None

        # ---- Plate selection ----
        roi_ok = bool(
            ctx.roi_plate_result and ctx.roi_plate_result.get("ok")
        )
        full_ok = bool(
            ctx.full_plate_result and ctx.full_plate_result.get("ok")
        )

        selected_plate: Dict[str, Any]
        plate_source: Optional[str] = None

        if roi_ok:
            selected_plate = ctx.roi_plate_result  # type: ignore[assignment]
            plate_source = "roi"
            if (
                full_ok
                and ctx.full_plate_result.get("plate_code")
                != ctx.roi_plate_result.get("plate_code")
            ):
                ctx.warnings.append(
                    "全图 OCR 与 ROI OCR 标识不一致，已按 ROI OCR 结果输出"
                )
        elif full_ok:
            selected_plate = ctx.full_plate_result  # type: ignore[assignment]
            plate_source = "full_image"
            if ctx.roi_plate_result is not None and not ctx.roi_plate_result.get("ok"):
                ctx.warnings.append(
                    "ROI OCR 未识别出像质计标识，已回退到全图 OCR 结果"
                )
        elif ctx.roi_plate_result is not None:
            selected_plate = ctx.roi_plate_result
        else:
            selected_plate = ctx.full_plate_result or {}

        selected_plate = dict(selected_plate)

        # ---- Update field statistics ----
        ctx.field_statistics["roi_marker_found"] = bool(
            ctx.roi_plate_result and ctx.roi_plate_result.get("ok")
        )
        ctx.field_statistics["iqi_marker_found"] = bool(
            selected_plate.get("ok")
        )
        ctx.plate_result = selected_plate
        ctx.plate_source = plate_source

        # ---- Determine ROI error ----
        if not ctx.roi_info or not ctx.roi_info.get("polygon"):
            roi_error_code = 1101
            roi_error_message = "未检测到像质计 ROI"
            ctx.wire_result = build_skipped_wire(
                "skipped_no_roi", roi_error_message
            )
        elif ctx.roi_gray is None or not ctx.roi_info.get("crop_inverse_matrix"):
            roi_error_code = 1102
            roi_error_message = "像质计 ROI 透视展开失败"
            ctx.wire_result = build_skipped_wire(
                "skipped_roi_invalid", roi_error_message
            )

        # ---- Wire error entries ----
        wire_error_entries: List[Dict[str, Any]] = []
        wire = ctx.wire_result or {}
        if roi_error_code is None:
            # Wire inference should have run or been skipped
            if wire.get("status") != "ok":
                wire_error_entries.append(
                    {
                        "stage": "wire",
                        **build_result_status(
                            3001,
                            wire.get("error") or "像质丝识别失败",
                        ),
                    }
                )
            elif wire.get("wire_count") is None:
                wire_error_entries.append(
                    {
                        "stage": "wire",
                        **build_result_status(3002),
                    }
                )

        # ---- Compile error entries ----
        error_entries: List[Dict[str, Any]] = list(wire_error_entries)

        # ROI error takes precedence
        if roi_error_code is not None:
            error_entries.insert(
                0,
                {
                    "stage": "roi",
                    **build_result_status(roi_error_code, roi_error_message),
                },
            )

        # Marker error
        if not selected_plate.get("ok"):
            error_entries.append(
                {
                    "stage": "marker",
                    **build_result_status(
                        int(selected_plate.get("result_code", 9001))
                    ),
                }
            )

        # ---- Compute grade ----
        grade_result: Optional[Dict[str, Any]] = None
        if selected_plate.get("ok") and wire.get("status") == "ok" and roi_error_code is None:
            grade_result = compute_iqi_grade(
                selected_plate.get("iqi_type"),
                selected_plate.get("number"),
                wire.get("wire_count"),
                allowed_numbers=allowed_numbers,
            )
            if not grade_result.get("ok"):
                error_entries.append(
                    {
                        "stage": "grade",
                        **build_result_status(
                            int(grade_result.get("result_code", 9001))
                        ),
                    }
                )

        ctx.grade_result = grade_result
        ctx.record_errors = error_entries
        ctx.plate_result = selected_plate
        ctx.plate_source = plate_source

        logger.info(
            "stage_done",
            extra={
                "stage": self.name,
                "plate_source": plate_source,
                "grade": grade_result.get("grade") if grade_result else None,
                "marker_ok": bool(selected_plate.get("ok")),
                "error_count": len(error_entries),
            },
        )
        return ctx
