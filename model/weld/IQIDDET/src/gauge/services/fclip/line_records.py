"""Line coordinate helper functions for FClip wire inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np

from gauge.imaging.geometry import (
    invert_perspective_matrix,
    perspective_transform_points,
    undo_ccw90_points,
)
from gauge.models.wire import LineRecord, WireResult


def resolve_torch_device(device: Optional[str]):
    import torch

    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _ensure_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.ndim == 3 and image.shape[2] == 1:
        return image[:, :, 0]
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def lines_yx_to_xy(lines: np.ndarray) -> np.ndarray:
    if lines.size == 0:
        return np.zeros((0, 2, 2), dtype=np.float32)
    arr = np.asarray(lines, dtype=np.float32)
    swapped = arr[..., ::-1].copy()
    return swapped


def build_line_records(
    lines_yx: np.ndarray,
    scores: Sequence[float],
    crop_inverse_matrix: Optional[np.ndarray] = None,
    pre_rotate_size: Optional[Sequence[int]] = None,
    rotated: bool = False,
) -> List[Dict[str, Any]]:
    lines_xy = lines_yx_to_xy(lines_yx)
    records: List[Dict[str, Any]] = []
    for index, line_xy in enumerate(lines_xy):
        roi_points = np.asarray(line_xy, dtype=np.float32).reshape(2, 2)
        roi_unrotated = roi_points
        if rotated:
            if pre_rotate_size is None:
                raise ValueError("pre_rotate_size is required when rotated=True")
            roi_unrotated = undo_ccw90_points(roi_points, pre_rotate_size=pre_rotate_size)

        image_points: Optional[np.ndarray] = None
        if crop_inverse_matrix is not None:
            image_points = perspective_transform_points(roi_unrotated, crop_inverse_matrix)

        score = None
        if index < len(scores):
            score = float(scores[index])
        record_data = {
            "index": int(index),
            "score": score,
            "roi_xy": [[float(pt[0]), float(pt[1])] for pt in roi_points],
            "roi_unrotated_xy": [[float(pt[0]), float(pt[1])] for pt in roi_unrotated],
            "image_xy": None,
        }
        if image_points is not None:
            record_data["image_xy"] = [[float(pt[0]), float(pt[1])] for pt in image_points]
        records.append(LineRecord(**record_data).model_dump())
    return records
