#!/usr/bin/env python3
"""Builders for IQI records, delivery payloads, and batch statistics."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from gauge.domain.iqi_rules import (
    build_result_status,
    choose_primary_result_code,
    infer_plate_from_texts,
    normalize_text,
    parse_allowed_numbers_spec,
    summarize_result_codes,
    summarize_result_codes_named,
)
from gauge.models.record import IQIRecord


# ---------------------------------------------------------------------------
# Skipped/unavailable state builders (used by pipeline stages)
# ---------------------------------------------------------------------------


def build_skipped_ocr(status: str, error: Optional[str] = None) -> Dict[str, Any]:
    """Build a placeholder OCR result when OCR is skipped."""
    payload: Dict[str, Any] = {
        "status": str(status),
        "texts": [],
        "scores": [],
        "items": [],
        "all_items": [],
        "num_items": 0,
        "selected_variant": str(status),
        "all_texts_original": [],
        "all_texts_mirror": [],
        "det_box_count": 0,
        "rec_item_count": 0,
        "jb_items": [],
        "jb_texts": [],
        "jb_item_count": 0,
        "item_errors": [],
        "timings_ms": {
            "text_det_ms": 0.0,
            "text_orientation_ms": 0.0,
            "text_rec_ms": 0.0,
            "text_total_ms": 0.0,
        },
    }
    if error:
        payload["error"] = str(error)
    return payload


def build_skipped_wire(status: str, error: Optional[str] = None) -> Dict[str, Any]:
    """Build a placeholder wire result when wire inference is skipped."""
    payload: Dict[str, Any] = {
        "status": str(status),
        "wire_count": None,
        "parsed_line_count": 0,
        "lines": [],
        "warnings": [],
    }
    if error:
        payload["error"] = str(error)
    return payload


def _optional_section(value: Any) -> Any:
    if isinstance(value, dict) and not value:
        return None
    return value


def build_iqi_record(ctx: Any) -> IQIRecord:
    primary_code = choose_primary_result_code(
        [entry["result_code"] for entry in ctx.record_errors]
    )
    status = build_result_status(primary_code)

    plate = ctx.plate_result or {}
    wire = ctx.wire_result or {}
    selected_plate_source = ctx.plate_source

    rec_plate = dict(plate)
    if selected_plate_source == "roi":
        rec_plate["raw_text_items"] = list(ctx.roi_plate_vis_items or [])
    elif selected_plate_source == "full_image":
        rec_plate["raw_text_items"] = list(ctx.full_plate_vis_items or [])
    else:
        rec_plate.setdefault("raw_text_items", [])

    return IQIRecord(
        image_path=ctx.image_path,
        ok=primary_code == 0,
        status="ok" if primary_code == 0 else "error",
        result_code=primary_code,
        result_name=status["result_name"],
        result_message=status["result_message"],
        grade=int(ctx.grade_result["grade"])
        if primary_code == 0
        and ctx.grade_result is not None
        and ctx.grade_result.get("grade") is not None
        else None,
        iqi_type=plate.get("iqi_type"),
        plate_code=plate.get("plate_code"),
        plate_number=plate.get("number"),
        plate_source=selected_plate_source,
        wire_count=wire.get("wire_count"),
        width=ctx.width,
        height=ctx.height,
        general_fields_found=bool(
            ctx.field_statistics.get("general_fields_found", False)
        ),
        iqi_marker_found=bool(plate.get("ok", False)),
        fields=(
            ctx.general_fields_data.get("fields")
            if isinstance(ctx.general_fields_data.get("fields"), dict)
            else {}
        ),
        field_statistics=dict(ctx.field_statistics),
        correction=dict(ctx.correction_info),
        full_image_preprocess=build_full_image_preprocess(ctx),
        preprocess=build_roi_preprocess(ctx),
        ocr=ctx.full_ocr_result,
        full_image_ocr=ctx.full_ocr_result,
        full_image_plate=ctx.full_plate_result,
        roi=_optional_section(ctx.roi_info),
        roi_ocr=ctx.roi_ocr_result,
        roi_plate=ctx.roi_plate_result,
        plate=rec_plate,
        wire=wire,
        grade_rule=ctx.grade_result,
        warnings=list(ctx.warnings),
        errors=list(ctx.record_errors),
        visualization=build_visualization(ctx),
        timings_ms=dict(ctx.timings_ms),
    )


def build_full_image_preprocess(ctx: Any) -> Dict[str, Any]:
    if ctx.full_ocr_result is None:
        return {}
    config = ctx.config
    return {
        "resize_scale": float(ctx.resize_scale),
        "resize_long_side": int(config.ocr.det_limit_side_len),
        "sampled_size": (
            [int(ctx.sampled_image.shape[1]), int(ctx.sampled_image.shape[0])]
            if ctx.sampled_image is not None
            else None
        ),
        "ocr_enhance_mode": "windowing",
    }


def build_roi_preprocess(ctx: Any) -> Dict[str, Any]:
    if ctx.roi_image is None:
        return {}
    return {
        "rotation": 90 if ctx.rotated else 0,
        "rotated": bool(ctx.rotated),
        "enhance_mode": ctx.config.enhance.mode,
        "roi_size": (
            [int(ctx.roi_image.shape[1]), int(ctx.roi_image.shape[0])]
            if ctx.roi_image is not None
            else None
        ),
    }


def build_visualization(ctx: Any) -> Dict[str, Any]:
    plate = ctx.plate_result or {}
    wire = ctx.wire_result or {}
    roi = ctx.roi_info or {}

    if ctx.plate_source == "roi":
        plate_items = list(ctx.roi_plate_vis_items or [])
    elif ctx.plate_source == "full_image":
        plate_items = list(ctx.full_plate_vis_items or [])
    else:
        plate_items = []

    allowed_numbers = parse_allowed_numbers_spec(ctx.config.ocr.number_range)
    target_code = normalize_text(plate.get("plate_code"))
    plate_items_selected: List[Dict[str, Any]] = []
    if target_code:
        for item in plate_items:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            parsed = infer_plate_from_texts(
                [text],
                require_jb=True,
                allowed_numbers=allowed_numbers,
            )
            candidates = [
                normalize_text(code)
                for code in (parsed.get("candidate_codes") or [])
            ]
            if target_code in candidates:
                plate_items_selected.append(item)

    wire_lines = []
    for line in wire.get("lines") or []:
        image_xy = line.get("image_xy")
        if not image_xy:
            continue
        wire_lines.append(
            {
                "index": line.get("index"),
                "score": line.get("score"),
                "image_xy": image_xy,
            }
        )

    return {
        "roi_polygon_xy": roi.get("polygon"),
        "roi_bbox": roi.get("bbox"),
        "plate_source": ctx.plate_source,
        "plate_code": plate.get("plate_code"),
        "candidate_codes": plate.get("candidate_codes") or [],
        "raw_texts": plate.get("raw_texts") or [],
        "plate_text_items": plate_items,
        "plate_text_items_selected": plate_items_selected,
        "wire_lines": wire_lines,
    }


def build_iqi_statistics(results: Sequence[Dict[str, Any]], topk: int = 200) -> Dict[str, Any]:
    from gauge.domain.statistics import build_ocr_statistics

    ocr_stats = build_ocr_statistics(list(results), topk=topk)
    grade_counter = Counter()
    type_counter = Counter()
    field_totals = Counter()
    ok_total = 0
    failure_total = 0
    images_with_general_fields = 0
    images_with_iqi_marker = 0

    for record in results:
        if record.get("ok"):
            ok_total += 1
            if record.get("grade") is not None:
                grade_counter[str(int(record["grade"]))] += 1
        else:
            failure_total += 1
        if record.get("iqi_type"):
            type_counter[str(record["iqi_type"])] += 1

        field_stats = record.get("field_statistics") or {}
        if field_stats.get("general_fields_found"):
            images_with_general_fields += 1
        if field_stats.get("iqi_marker_found"):
            images_with_iqi_marker += 1

        fields = record.get("fields") or {}
        field_totals["component_codes"] += len(fields.get("component_codes") or [])
        field_totals["weld_film_pairs"] += len(fields.get("weld_film_pairs") or [])
        field_totals["weld_numbers"] += len(fields.get("weld_numbers") or [])
        field_totals["film_numbers"] += len(fields.get("film_numbers") or [])
        field_totals["pipe_specs"] += len(fields.get("pipe_specs") or [])

    return {
        "images_total": len(results),
        "success_total": int(ok_total),
        "failure_total": int(failure_total),
        "result_code_hist": summarize_result_codes(results),
        "result_code_hist_named": summarize_result_codes_named(results),
        "iqi_type_hist": {key: int(value) for key, value in sorted(type_counter.items())},
        "grade_hist": {key: int(value) for key, value in sorted(grade_counter.items(), key=lambda item: int(item[0]))},
        "field_totals": {key: int(value) for key, value in sorted(field_totals.items())},
        "images_with_general_fields": int(images_with_general_fields),
        "images_with_iqi_marker": int(images_with_iqi_marker),
        "ocr_stats": ocr_stats,
    }


def build_delivery_record(record: Dict[str, Any]) -> Dict[str, Any]:
    visualization = record.get("visualization") or {}
    fields = record.get("fields") or {}
    plate_text_items_selected = []
    for item in visualization.get("plate_text_items_selected") or []:
        plate_text_items_selected.append(
            {
                "text": item.get("text"),
                "score": item.get("score"),
                "box_image_xy": item.get("box_image_xy"),
            }
        )
    payload = {
        "image_path": record.get("image_path"),
        "ok": bool(record.get("ok", False)),
        "result_code": int(record.get("result_code", 9001)),
        "result_name": record.get("result_name"),
        "result_message": record.get("result_message"),
        "grade": record.get("grade"),
        "iqi_type": record.get("iqi_type"),
        "plate_code": record.get("plate_code"),
        "plate_number": record.get("plate_number"),
        "plate_source": record.get("plate_source"),
        "wire_count": record.get("wire_count"),
        "general_fields_found": bool(record.get("general_fields_found", False)),
        "iqi_marker_found": bool(record.get("iqi_marker_found", False)),
        "visualization": {
            "roi_polygon_xy": visualization.get("roi_polygon_xy"),
            "plate_text_items_selected": plate_text_items_selected,
            "wire_lines": visualization.get("wire_lines") or [],
        },
        "fields": {
            "component_codes": fields.get("component_codes") or [],
            "weld_film_pairs": fields.get("weld_film_pairs") or [],
            "weld_numbers": fields.get("weld_numbers") or [],
            "film_numbers": fields.get("film_numbers") or [],
            "pipe_specs": fields.get("pipe_specs") or [],
        },
        "field_statistics": record.get("field_statistics") or {},
        "warnings": record.get("warnings") or [],
        "errors": record.get("errors") or [],
    }
    if record.get("final_result_vis_path"):
        payload["final_result_vis_path"] = record.get("final_result_vis_path")
    if record.get("status_vis_dir"):
        payload["status_vis_dir"] = record.get("status_vis_dir")
    return payload
