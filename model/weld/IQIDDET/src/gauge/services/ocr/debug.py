#!/usr/bin/env python3
"""Debug drawing helpers for OCR results."""

from __future__ import annotations

from typing import Any, Dict, List

import cv2
import numpy as np

from gauge.imaging.preprocess import crop_rotated_polygon


def draw_ocr_on_roi(roi_image: np.ndarray, ocr_result: Dict[str, Any]) -> np.ndarray:
    """Draw OCR polygons and texts on ROI image."""
    vis = roi_image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    items = ocr_result.get("all_items") or ocr_result.get("items", []) or []
    for item in items:
        box = item.get("box")
        text = str(item.get("text", ""))
        score = item.get("score")
        if box is None:
            continue
        try:
            pts = np.array(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            continue
        if pts.shape[0] < 3:
            continue
        pts_i = pts.astype(np.int32).reshape(-1, 1, 2)
        color = (0, 255, 0) if item.get("status") != "error" else (0, 0, 255)
        cv2.polylines(vis, [pts_i], isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA)

        label = text or f"[{item.get('status', 'empty')}]"
        if score is not None:
            label = f"{label} ({float(score):.2f})"
        x = int(np.min(pts[:, 0]))
        y = int(np.min(pts[:, 1])) - 6
        y = max(y, 18)
        cv2.putText(
            vis,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    return vis


def draw_recognition_result(crop_image: np.ndarray, item: Dict[str, Any]) -> np.ndarray:
    """Draw recognized text and optional orientation action under a crop image."""
    vis = crop_image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    text = str(item.get("text", "")) or f"[{item.get('status', 'empty')}]"
    score = item.get("score")
    orientation = item.get("orientation") or {}
    actions = orientation.get("actions") if orientation.get("corrected") else None

    lines = [text if score is None else f"{text} ({float(score):.2f})"]
    if actions:
        lines.append(str(actions))

    line_height = 24
    footer_height = line_height * len(lines) + 12
    canvas = np.full((vis.shape[0] + footer_height, vis.shape[1], 3), 255, dtype=np.uint8)
    canvas[: vis.shape[0], : vis.shape[1]] = vis

    y = vis.shape[0] + 22
    for line in lines:
        cv2.putText(
            canvas,
            line,
            (8, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            lineType=cv2.LINE_AA,
        )
        y += line_height
    return canvas


def build_ocr_item_debug_images(roi_image: np.ndarray, ocr_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rebuild crop / corrected crop / rec vis images from OCR result metadata."""
    debug_rows: List[Dict[str, Any]] = []
    items = ocr_result.get("all_items", []) or []
    for item in items:
        box = item.get("box")
        if box is None:
            continue
        try:
            pts = np.array(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            continue
        crop, _ = crop_rotated_polygon(roi_image, pts)
        if crop is None:
            continue

        rec_input = crop.copy()
        orientation = item.get("orientation") or {}
        label = orientation.get("label")
        if label is not None and orientation.get("status") != "disabled":
            from gauge.services.orientation.ocr_text import OCRTextOrientationCorrector

            rec_input, _ = OCRTextOrientationCorrector.restore_image(crop, int(label))

        debug_rows.append(
            {
                "crop_index": int(item.get("crop_index", len(debug_rows))),
                "crop_image": crop,
                "rec_input_image": rec_input,
                "rec_result_image": draw_recognition_result(rec_input, item),
                "text": item.get("text", ""),
                "score": item.get("score"),
            }
        )
    return debug_rows
