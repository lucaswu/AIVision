#!/usr/bin/env python3
"""Shared helpers for the gauge pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def collect_images(
    image_dir: Optional[Path],
    image_list: Optional[Path],
    max_images: Optional[int] = None,
) -> List[Path]:
    paths: List[Path] = []
    if image_list is not None:
        base = image_list.parent
        lines = image_list.read_text(encoding="utf-8").splitlines()
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            item = Path(line)
            if not item.is_absolute():
                item = (base / item).resolve()
            if item.is_dir():
                paths.extend(sorted(p for p in item.rglob("*") if p.suffix.lower() in SUPPORTED_IMAGE_EXTS))
            else:
                paths.append(item)
    elif image_dir is not None:
        paths = sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in SUPPORTED_IMAGE_EXTS)
    else:
        raise ValueError("image_dir or image_list must be provided.")

    if max_images is not None:
        paths = paths[:max_images]
    if not paths:
        root = image_dir if image_dir is not None else image_list
        raise FileNotFoundError(f"No supported images found under {root}")
    return paths


def load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Failed to read image: {path}")
    return image


def resize_long_side(image: np.ndarray, target_long_side: Optional[int]) -> Tuple[np.ndarray, float]:
    if target_long_side is None:
        return image, 1.0
    target = int(target_long_side)
    if target <= 0:
        return image, 1.0
    h, w = image.shape[:2]
    long_side = max(h, w)
    if long_side <= target:
        return image, 1.0
    scale = float(target) / float(long_side)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


def order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def crop_rotated_polygon(image: np.ndarray, polygon: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    box = order_points(polygon.astype(np.float32))
    w1 = np.linalg.norm(box[0] - box[1])
    w2 = np.linalg.norm(box[2] - box[3])
    h1 = np.linalg.norm(box[0] - box[3])
    h2 = np.linalg.norm(box[1] - box[2])
    width = int(round(max(w1, w2)))
    height = int(round(max(h1, h2)))
    if width < 2 or height < 2:
        return None, None
    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(box, dst)
    warped = cv2.warpPerspective(image, matrix, (width, height))
    return warped, matrix


def rotate_if_wide(image: np.ndarray, enable: bool = True) -> Tuple[np.ndarray, bool, int]:
    if not enable:
        return image, False, 0
    h, w = image.shape[:2]
    if w > h:
        rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return rotated, True, 90
    return image, False, 0


def auto_window_level(image: np.ndarray) -> Tuple[int, int]:
    percentiles = np.percentile(image, [2, 98])
    img_min, img_max = percentiles[0], percentiles[1]
    img_mean = np.mean(image)
    img_std = np.std(image)
    window_level = int(img_mean)
    window_width = int(min(4 * img_std, img_max - img_min))
    window_width = max(1, window_width)
    return window_width, window_level


def apply_window_level(image: np.ndarray, window_width: int, window_level: int) -> np.ndarray:
    window_min = window_level - window_width / 2
    window_max = window_level + window_width / 2
    if window_max <= window_min:
        window_max = window_min + 1
    output = np.clip((image - window_min) / window_width * 255.0, 0, 255).astype(np.uint8)
    return output


def apply_clahe(image: np.ndarray, clip_limit: float = 2.0, tile_grid_size=(8, 8)) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(image)


def enhance_windowing_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    img_float = gray.astype(np.float32, copy=False)
    ww, wl = auto_window_level(img_float)
    enhanced = apply_window_level(img_float, ww, wl)
    enhanced = apply_clahe(enhanced)
    return enhanced


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def format_polygon(points: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[float(x), float(y)] for x, y in points]


def safe_list(values: Iterable[float]) -> List[float]:
    return [float(v) for v in values]
