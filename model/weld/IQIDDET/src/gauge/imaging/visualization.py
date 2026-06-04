#!/usr/bin/env python3
"""Debug and final-result visualization helpers for IQI inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np

from gauge.imaging.geometry import box_points_to_bbox, is_usable_ocr_item
from gauge.imaging.preprocess import ensure_dir
from gauge.services.ocr.debug import build_ocr_item_debug_images, draw_ocr_on_roi
from gauge.services.roi.yolo_obb import build_roi_vis_image


def build_wire_vis_image(roi_image: np.ndarray, wire_result: Dict[str, Any]) -> np.ndarray:
    vis = roi_image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    for line in wire_result.get("lines") or []:
        points = line.get("roi_xy") or []
        if len(points) != 2:
            continue
        p0 = (int(round(points[0][0])), int(round(points[0][1])))
        p1 = (int(round(points[1][0])), int(round(points[1][1])))
        cv2.line(vis, p0, p1, (0, 0, 255), 2, lineType=cv2.LINE_AA)
    text = f"wire_count={wire_result.get('wire_count')} parsed={wire_result.get('parsed_line_count')}"
    cv2.putText(vis, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)
    return vis


def build_final_result_vis_image(
    image: np.ndarray,
    visualization: Optional[Dict[str, Any]] = None,
    plate_code: Optional[str] = None,
    grade: Optional[int] = None,
    wire_count: Optional[int] = None,
) -> np.ndarray:
    vis = image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    visualization = dict(visualization or {})

    roi_polygon = visualization.get("roi_polygon_xy") or []
    try:
        roi_pts = np.asarray(roi_polygon, dtype=np.float32).reshape(-1, 2)
    except Exception:
        roi_pts = np.zeros((0, 2), dtype=np.float32)
    if roi_pts.shape[0] >= 3:
        cv2.polylines(
            vis,
            [roi_pts.astype(np.int32).reshape(-1, 1, 2)],
            isClosed=True,
            color=(0, 255, 0),
            thickness=3,
            lineType=cv2.LINE_AA,
        )

    plate_text_items = (
        visualization.get("plate_text_items_selected")
        or visualization.get("plate_text_items")
        or []
    )
    for item in plate_text_items:
        box = item.get("box_image_xy") or []
        try:
            pts = np.asarray(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            continue
        if pts.shape[0] < 3:
            continue
        cv2.polylines(
            vis,
            [pts.astype(np.int32).reshape(-1, 1, 2)],
            isClosed=True,
            color=(0, 215, 255),
            thickness=2,
            lineType=cv2.LINE_AA,
        )
        label = str(item.get("text", "")).strip() or "[empty]"
        score = item.get("score")
        if score is not None:
            label = f"{label} ({float(score):.2f})"
        x = int(np.min(pts[:, 0]))
        y = max(20, int(np.min(pts[:, 1])) - 8)
        cv2.putText(
            vis,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 215, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    for line in visualization.get("wire_lines") or []:
        points = line.get("image_xy") or []
        if len(points) != 2:
            continue
        p0 = (int(round(points[0][0])), int(round(points[0][1])))
        p1 = (int(round(points[1][0])), int(round(points[1][1])))
        cv2.line(vis, p0, p1, (0, 0, 255), 2, lineType=cv2.LINE_AA)

    summary_lines = []
    if plate_code:
        summary_lines.append(f"plate={plate_code}")
    if grade is not None:
        summary_lines.append(f"grade={grade}")
    if wire_count is not None:
        summary_lines.append(f"wire_count={wire_count}")
    if summary_lines:
        cv2.putText(
            vis,
            "  ".join(summary_lines),
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2,
            lineType=cv2.LINE_AA,
        )

    return vis


def save_debug_visualizations(
    output_dir: Path,
    sample_dir: Path,
    image: np.ndarray,
    full_ocr_result: Dict[str, Any],
    full_ocr_image: Optional[np.ndarray] = None,
    roi_info: Optional[Dict[str, Any]] = None,
    roi_image: Optional[np.ndarray] = None,
    roi_gray: Optional[np.ndarray] = None,
    roi_ocr_result: Optional[Dict[str, Any]] = None,
    wire_result: Optional[Dict[str, Any]] = None,
    visualization: Optional[Dict[str, Any]] = None,
    plate_code: Optional[str] = None,
    grade: Optional[int] = None,
    wire_count: Optional[int] = None,
) -> Dict[str, Any]:
    ensure_dir(sample_dir)

    input_path = sample_dir / "input.png"
    cv2.imwrite(str(input_path), image)

    payload: Dict[str, Any] = {
        "status_vis_dir": str(sample_dir.relative_to(output_dir)),
        "input_vis_path": str(input_path.relative_to(output_dir)),
    }

    full_base = full_ocr_image if full_ocr_image is not None else image
    full_input_path = sample_dir / "full_ocr_input.png"
    cv2.imwrite(str(full_input_path), full_base)
    full_ocr_vis = draw_ocr_on_roi(full_base, full_ocr_result)
    full_ocr_vis_path = sample_dir / "full_ocr_result.png"
    cv2.imwrite(str(full_ocr_vis_path), full_ocr_vis)

    full_item_vis_rows: List[Dict[str, Any]] = []
    full_debug_rows = build_ocr_item_debug_images(full_base, full_ocr_result)
    if full_debug_rows:
        item_dir = sample_dir / "full_ocr_items"
        ensure_dir(item_dir)
        for row in full_debug_rows:
            crop_index = int(row.get("crop_index", len(full_item_vis_rows)))
            crop_path = item_dir / f"crop_{crop_index:03d}.png"
            rec_input_path = item_dir / f"rec_input_{crop_index:03d}.png"
            rec_result_path = item_dir / f"rec_result_{crop_index:03d}.png"
            cv2.imwrite(str(crop_path), row["crop_image"])
            cv2.imwrite(str(rec_input_path), row["rec_input_image"])
            cv2.imwrite(str(rec_result_path), row["rec_result_image"])
            full_item_vis_rows.append(
                {
                    "crop_index": crop_index,
                    "crop_path": str(crop_path.relative_to(output_dir)),
                    "rec_input_path": str(rec_input_path.relative_to(output_dir)),
                    "rec_result_path": str(rec_result_path.relative_to(output_dir)),
                    "text": row.get("text", ""),
                    "score": row.get("score"),
                }
            )

    payload.update(
        {
            "full_ocr_input_path": str(full_input_path.relative_to(output_dir)),
            "full_ocr_vis_path": str(full_ocr_vis_path.relative_to(output_dir)),
            "full_ocr_item_vis": full_item_vis_rows,
            "ocr_vis_path": str(full_ocr_vis_path.relative_to(output_dir)),
            "ocr_item_vis": full_item_vis_rows,
        }
    )

    if roi_info:
        roi_vis = build_roi_vis_image(image, roi_info)
        roi_vis_path = sample_dir / "ROI.png"
        cv2.imwrite(str(roi_vis_path), roi_vis)
        payload["roi_vis_path"] = str(roi_vis_path.relative_to(output_dir))

    if roi_image is not None:
        roi_image_path = sample_dir / "roi_image.png"
        cv2.imwrite(str(roi_image_path), roi_image)
        payload["roi_image_path"] = str(roi_image_path.relative_to(output_dir))

    if roi_gray is not None:
        roi_gray_path = sample_dir / "roi_gray.png"
        cv2.imwrite(str(roi_gray_path), roi_gray)
        payload["roi_gray_path"] = str(roi_gray_path.relative_to(output_dir))

    if roi_ocr_result is not None and roi_gray is not None:
        roi_ocr_vis = draw_ocr_on_roi(roi_gray, roi_ocr_result)
        roi_ocr_vis_path = sample_dir / "roi_ocr_result.png"
        cv2.imwrite(str(roi_ocr_vis_path), roi_ocr_vis)
        payload["roi_ocr_vis_path"] = str(roi_ocr_vis_path.relative_to(output_dir))

        roi_item_vis_rows: List[Dict[str, Any]] = []
        roi_debug_rows = build_ocr_item_debug_images(roi_gray, roi_ocr_result)
        if roi_debug_rows:
            item_dir = sample_dir / "roi_ocr_items"
            ensure_dir(item_dir)
            for row in roi_debug_rows:
                crop_index = int(row.get("crop_index", len(roi_item_vis_rows)))
                crop_path = item_dir / f"crop_{crop_index:03d}.png"
                rec_input_path = item_dir / f"rec_input_{crop_index:03d}.png"
                rec_result_path = item_dir / f"rec_result_{crop_index:03d}.png"
                cv2.imwrite(str(crop_path), row["crop_image"])
                cv2.imwrite(str(rec_input_path), row["rec_input_image"])
                cv2.imwrite(str(rec_result_path), row["rec_result_image"])
                roi_item_vis_rows.append(
                    {
                        "crop_index": crop_index,
                        "crop_path": str(crop_path.relative_to(output_dir)),
                        "rec_input_path": str(rec_input_path.relative_to(output_dir)),
                        "rec_result_path": str(rec_result_path.relative_to(output_dir)),
                        "text": row.get("text", ""),
                        "score": row.get("score"),
                    }
                )
            payload["roi_ocr_item_vis"] = roi_item_vis_rows

    if wire_result is not None and roi_image is not None:
        wire_vis = build_wire_vis_image(roi_image, wire_result)
        wire_vis_path = sample_dir / "wire_result.png"
        cv2.imwrite(str(wire_vis_path), wire_vis)
        payload["wire_vis_path"] = str(wire_vis_path.relative_to(output_dir))

    if visualization:
        final_result_vis = build_final_result_vis_image(
            image=image,
            visualization=visualization,
            plate_code=plate_code,
            grade=grade,
            wire_count=wire_count,
        )
        final_result_path = sample_dir / "finalresult.png"
        cv2.imwrite(str(final_result_path), final_result_vis)
        payload["final_result_vis_path"] = str(final_result_path.relative_to(output_dir))

    return payload


def build_plate_visualization_items(
    items: Sequence[Dict[str, Any]],
    source: str,
) -> List[Dict[str, Any]]:
    """Build visualization-ready plate items from OCR items."""
    from gauge.domain.iqi_rules import normalize_text

    vis_items: List[Dict[str, Any]] = []
    text_index = 0
    for item in items:
        if not is_usable_ocr_item(item):
            continue
        box_image = item.get("box_image")
        if box_image is None:
            box_image = item.get("box")
        vis_items.append(
            {
                "text_index": int(text_index),
                "crop_index": item.get("crop_index"),
                "source": str(source),
                "text": str(item.get("text", "")),
                "normalized_text": normalize_text(item.get("text", "")),
                "score": item.get("score"),
                "det_score": item.get("det_score"),
                "status": item.get("status"),
                "accepted_by_score": bool(item.get("accepted_by_score", True)),
                "box_image_xy": box_image,
                "bbox_image": box_points_to_bbox(box_image),
                "box_roi_xy": item.get("box") if source == "roi" else None,
                "bbox_roi": box_points_to_bbox(item.get("box")) if source == "roi" else None,
            }
        )
        text_index += 1
    return vis_items
