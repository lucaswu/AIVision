#!/usr/bin/env python3
"""Shared ROI helpers for gauge detection workflows."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from gauge.pipeline_utils import format_polygon


def extract_best_obb(result: Any, select: str, class_filter: Optional[int]) -> Optional[Dict[str, Any]]:
    obb = getattr(result, "obb", None)
    if obb is None:
        return None

    polys = getattr(obb, "xyxyxyxy", None)
    if polys is None:
        return None
    polys = polys.detach().cpu().numpy()
    if polys.ndim == 2 and polys.shape[1] == 8:
        polys = polys.reshape(-1, 4, 2)

    confs = getattr(obb, "conf", None)
    confs_np = confs.detach().cpu().numpy() if confs is not None else None
    classes = getattr(obb, "cls", None)
    classes_np = classes.detach().cpu().numpy().astype(int) if classes is not None else None

    candidates = []
    for idx, poly in enumerate(polys):
        if class_filter is not None and classes_np is not None and classes_np[idx] != class_filter:
            continue
        area = float(cv2.contourArea(poly.astype(np.float32)))
        candidates.append((idx, area))

    if not candidates:
        return None

    if select == "conf" and confs_np is not None:
        idx = int(max(candidates, key=lambda item: confs_np[item[0]])[0])
    else:
        idx = int(max(candidates, key=lambda item: item[1])[0])

    poly = polys[idx].astype(float)
    conf = float(confs_np[idx]) if confs_np is not None else None
    cls_id = int(classes_np[idx]) if classes_np is not None else None
    x_min = float(np.min(poly[:, 0]))
    y_min = float(np.min(poly[:, 1]))
    x_max = float(np.max(poly[:, 0]))
    y_max = float(np.max(poly[:, 1]))
    return {
        "polygon": format_polygon(poly),
        "bbox": [x_min, y_min, x_max, y_max],
        "conf": conf,
        "class_id": cls_id,
    }


def build_roi_vis_image(image: np.ndarray, roi_info: Dict[str, Any]) -> np.ndarray:
    vis = image.copy()
    polygon = np.array(roi_info.get("polygon", []), dtype=np.float32)
    if polygon.ndim == 2 and polygon.shape[1] == 2 and polygon.shape[0] >= 3:
        pts = polygon.reshape(-1, 1, 2).astype(np.int32)
        cv2.polylines(vis, [pts], isClosed=True, color=(0, 255, 0), thickness=2)
    return vis


def crop_polygon_region(image: np.ndarray, polygon: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    from gauge.pipeline_utils import crop_rotated_polygon

    return crop_rotated_polygon(image, polygon)
