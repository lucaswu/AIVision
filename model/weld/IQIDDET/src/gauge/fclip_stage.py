#!/usr/bin/env python3
"""FClip wire-count inference helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import torch

from FClip.config import M
from FClip.infer_utils import (
    build_infer_model,
    get_count_pred,
    infer_heatmaps,
    load_config_from_yaml,
    parse_lines_1d,
    preprocess_gray_image,
    scale_lines,
)


def resolve_torch_device(device: Optional[str]) -> torch.device:
    if device:
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _ensure_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.ndim == 3 and image.shape[2] == 1:
        return image[:, :, 0]
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _ensure_float32_matrix(matrix: Any) -> np.ndarray:
    arr = np.asarray(matrix, dtype=np.float32)
    return arr.reshape(3, 3)


def invert_perspective_matrix(matrix: Any) -> np.ndarray:
    mat = _ensure_float32_matrix(matrix)
    return np.linalg.inv(mat)


def undo_ccw90_points(points_xy: np.ndarray, pre_rotate_size: Sequence[int]) -> np.ndarray:
    width = float(pre_rotate_size[0])
    out = points_xy.astype(np.float32, copy=True)
    x_rot = out[:, 0].copy()
    y_rot = out[:, 1].copy()
    out[:, 0] = width - 1.0 - y_rot
    out[:, 1] = x_rot
    return out


def perspective_transform_points(points_xy: np.ndarray, matrix: Any) -> np.ndarray:
    pts = np.asarray(points_xy, dtype=np.float32).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(pts, _ensure_float32_matrix(matrix))
    return transformed.reshape(-1, 2)


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
        record = {
            "index": int(index),
            "score": score,
            "roi_xy": [[float(pt[0]), float(pt[1])] for pt in roi_points],
            "roi_unrotated_xy": [[float(pt[0]), float(pt[1])] for pt in roi_unrotated],
            "image_xy": None,
        }
        if image_points is not None:
            record["image_xy"] = [[float(pt[0]), float(pt[1])] for pt in image_points]
        records.append(record)
    return records


class FClipInferencer:
    """Torch-based FClip inferencer for wire count and line endpoints."""

    def __init__(
        self,
        ckpt_path: str,
        device: Optional[str] = None,
        model_config: str = "config/model.yaml",
        params_file: str = "params.yaml",
        threshold: Optional[float] = None,
    ):
        self.ckpt_path = str(Path(ckpt_path).resolve())
        self.model_config = str(Path(model_config).resolve())
        self.params_file = str(Path(params_file).resolve())
        self.device = resolve_torch_device(device)
        load_config_from_yaml(self.model_config, params_yaml=self.params_file, ckpt=self.ckpt_path)
        self.model = build_infer_model(self.device)
        self.threshold = float(getattr(M, "delta", 0.8) if threshold is None else threshold)
        self.nlines = int(getattr(M, "nlines", 7))
        self.resolution = int(getattr(M, "resolution", 64))
        self.ang_type = str(getattr(M, "ang_type", "radian"))
        self.input_resolution = (
            int(getattr(M, "input_resolution_w", self.resolution * 4)),
            int(getattr(M, "input_resolution_h", self.resolution * 4)),
        )
        image_cfg = getattr(M, "image", None)
        self.mean = float(image_cfg.mean[0]) if image_cfg is not None else 125.67842
        self.std = float(image_cfg.stddev[0]) if image_cfg is not None else 65.406591

    def infer(
        self,
        roi_image: np.ndarray,
        crop_inverse_matrix: Optional[np.ndarray] = None,
        pre_rotate_size: Optional[Sequence[int]] = None,
        rotated: bool = False,
    ) -> Dict[str, Any]:
        try:
            roi_gray = _ensure_gray(roi_image)
            image_tensor = preprocess_gray_image(
                roi_gray,
                input_resolution=self.input_resolution,
                mean=self.mean,
                std=self.std,
                device=self.device,
            )
            heatmaps = infer_heatmaps(self.model, image_tensor)
            count_pred = get_count_pred(heatmaps)
            if count_pred is None:
                return {
                    "status": "error",
                    "error": "FClip outputs missing count head.",
                    "wire_count": None,
                    "parsed_line_count": 0,
                    "lines": [],
                    "warnings": [],
                }

            wire_count = int(count_pred[0].item())
            lcmap = heatmaps["lcmap"][0]
            lcoff = heatmaps["lcoff"][0]
            angle = heatmaps["angle"][0]
            lines_t, scores_t = parse_lines_1d(
                lcmap=lcmap,
                lcoff=lcoff,
                angle=angle,
                threshold=self.threshold,
                nlines=self.nlines,
                resolution=self.resolution,
                ang_type=self.ang_type,
                count_pred=wire_count,
            )
            if isinstance(lines_t, torch.Tensor):
                lines_scaled = lines_t.clone()
            else:
                lines_scaled = torch.as_tensor(lines_t).clone()
            lines_scaled = scale_lines(lines_scaled, self.resolution, roi_gray.shape)
            lines_np = lines_scaled.detach().cpu().numpy() if isinstance(lines_scaled, torch.Tensor) else np.asarray(lines_scaled)
            scores_np = scores_t.detach().cpu().numpy() if isinstance(scores_t, torch.Tensor) else np.asarray(scores_t)
            line_records = build_line_records(
                lines_yx=lines_np,
                scores=scores_np.tolist(),
                crop_inverse_matrix=crop_inverse_matrix,
                pre_rotate_size=pre_rotate_size,
                rotated=rotated,
            )
            warnings: List[str] = []
            if wire_count != len(line_records):
                warnings.append(
                    f"wire_count={wire_count} 与 parsed_line_count={len(line_records)} 不一致，等级计算以 wire_count 为准"
                )
            return {
                "status": "ok",
                "wire_count": wire_count,
                "parsed_line_count": int(len(line_records)),
                "lines": line_records,
                "warnings": warnings,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "wire_count": None,
                "parsed_line_count": 0,
                "lines": [],
                "warnings": [],
            }
