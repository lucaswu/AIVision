#!/usr/bin/env python3
"""Backward-compatible IQI OCR helpers."""

from __future__ import annotations

from typing import Any, Sequence

import cv2
import numpy as np

from gauge.iqi_rules import compute_iqi_grade, infer_plate_from_texts


def _ensure_bgr(image: Any) -> Any:
    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.ndim == 3 and image.shape[2] == 1:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def run_paddle_ocr(ocr_engine: Any, image: Any):
    image = _ensure_bgr(image)
    try:
        return ocr_engine.predict(input=image)
    except TypeError:
        return ocr_engine.predict(image)


__all__ = [
    "compute_iqi_grade",
    "infer_plate_from_texts",
    "run_paddle_ocr",
]
