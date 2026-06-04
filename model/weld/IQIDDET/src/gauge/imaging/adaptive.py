#!/usr/bin/env python3
"""Adaptive preprocessing used by weld orientation correction."""

from __future__ import annotations

from typing import Dict, Tuple

import cv2
import numpy as np


class AdaptiveImageProcessor:
    """Apply windowing and optional negative transform to weld film images."""

    def __init__(self, use_negative: bool = True):
        self.use_negative = use_negative
        self.image_stats = None

    def analyze_image(self, image: np.ndarray) -> Dict[str, object]:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        mean = np.mean(gray)
        std = np.std(gray)
        min_val = np.min(gray)
        max_val = np.max(gray)

        percentiles = {
            "p1": np.percentile(gray, 1),
            "p5": np.percentile(gray, 5),
            "p25": np.percentile(gray, 25),
            "p75": np.percentile(gray, 75),
            "p95": np.percentile(gray, 95),
            "p99": np.percentile(gray, 99),
        }

        features = {
            "dynamic_range": max_val - min_val,
            "contrast": std / mean if mean > 0 else 0,
            "brightness": mean,
            "is_dark": mean < 85,
            "is_bright": mean > 170,
            "is_low_contrast": std < 30,
            "is_high_contrast": std > 80,
        }

        self.image_stats = {
            "mean": mean,
            "std": std,
            "min": min_val,
            "max": max_val,
            "percentiles": percentiles,
            "features": features,
        }
        return self.image_stats

    def auto_set_bone_metal_window(self) -> Tuple[int, int]:
        if not self.image_stats:
            return 128, 256

        stats = self.image_stats
        center = int(round(stats["mean"] + stats["std"]))
        width = int(round(stats["std"] * 6))
        center = max(0, min(255, center))
        width = max(100, min(512, width))
        return center, width

    def apply_windowing(self, image: np.ndarray, window_center: int, window_width: int) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        else:
            gray = image.astype(np.float32)

        min_value = window_center - window_width / 2
        max_value = window_center + window_width / 2
        windowed = np.where(
            gray <= min_value,
            0,
            np.where(
                gray >= max_value,
                255,
                ((gray - min_value) / window_width) * 255,
            ),
        )
        return windowed.astype(np.uint8)

    def apply_negative_transform(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        return (255 - gray).astype(np.uint8)

    def process_image(self, image: np.ndarray, apply_negative: bool | None = None) -> np.ndarray:
        if apply_negative is None:
            apply_negative = self.use_negative

        self.analyze_image(image)
        window_center, window_width = self.auto_set_bone_metal_window()
        windowed = self.apply_windowing(image, window_center, window_width)
        if apply_negative:
            return self.apply_negative_transform(windowed)
        return windowed
