#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weld Defect Position Detection Utility (Location 1)

This module provides functionality to detect defect positions (origin / mark
positions) in corrected weld film images using a YOLO detection model
from a YOLO detection model (location_1.pt).

The model detects five classes:
  - 'center_mark'   : center positioning mark
  - 'letter_left'   : left-side letter mark
  - 'letter_right'  : right-side letter mark
  - 'number_left'   : left-side number mark
  - 'number_right'  : right-side number mark

Pre-processing mirrors the training pipeline:
    AdaptiveImageProcessor(use_negative=True) → negative + windowing →
    adaptive sharpening.

The calculated origin (x, y) and positioning type are returned in the
detection result dict.
"""

import os
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Union

import cv2
import numpy as np


# Default model weight path relative to the weld module root (model/weld/)
_MODULE_DIR = Path(__file__).resolve().parent          # model/weld/utils/
_WELD_ROOT  = _MODULE_DIR.parent                       # model/weld/
DEFAULT_LOCATION1_MODEL_PATH = str(_WELD_ROOT / "weight" / "location_1.pt")

_CLASS_NAMES = [
    'center_mark',
    'letter_left',
    'letter_right',
    'number_left',
    'number_right',
]


class WeldDefectPositionDetector:
    """
    Weld defect position detector using a YOLO detection model.

    Input : color BGR image (corrected original, as returned by
            WeldOrientationCorrector).
    Pre-processing: adaptive preprocessing (negative + windowing + sharpening)
            identical to the training pipeline.
    Output: a single result dict containing the detected origin position,
            positioning type and raw detection list.

    Result dict schema::

        {
            "detected":          bool,
            "positioning_type":  int | None,   # 0=center, 1=edge, None=not detected
            "origin_x":          float | None,
            "origin_y":          float | None,
            "origin_text":       None,         # (Reserved for compatibility)
            "detections": [
                {
                    "class_id":   int,
                    "class_name": str,
                    "confidence": float,
                    "bbox":       [x1, y1, x2, y2],
                    "center_x":   float,
                    "center_y":   float,
                    "text":       str | None,
                },
                ...
            ]
        }
    """

    def __init__(self,
                 model_path: Union[str, Path] = DEFAULT_LOCATION1_MODEL_PATH,
                 conf_threshold: float = 0.25,
                 adaptive_processor_path: Optional[str] = None):
        """
        Initialize the weld defect position detector.
        """
        from ultralytics import YOLO  # lazy import

        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold

        # Load adaptive preprocessor
        self.processor = self._load_processor(adaptive_processor_path)

        # Load YOLO detection model
        self.model = YOLO(str(self.model_path))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_processor(self, filepath: Optional[str] = None):
        """
        Load AdaptiveImageProcessor from adaptive-image-processor.py.

        Search order:
          1. ``filepath`` (if provided)
          2. model/weld/adaptive-image-processor.py
          3. current working directory

        Returns:
            AdaptiveImageProcessor instance (use_negative=True), or None if
            the script cannot be found / loaded.
        """
        search_paths: List[str] = []
        if filepath:
            search_paths.append(filepath)
        search_paths.append(str(_WELD_ROOT / "adaptive-image-processor.py"))
        search_paths.append(os.path.join(os.getcwd(), "adaptive-image-processor.py"))

        for path in search_paths:
            if os.path.exists(path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "adaptive_image_processor", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    processor = module.AdaptiveImageProcessor(use_negative=True)
                    print(f"[WeldDefectPositionDetector] AdaptiveImageProcessor loaded: {path}")
                    return processor
                except Exception as exc:
                    print(f"[WeldDefectPositionDetector] Warning: cannot load processor "
                          f"({path}): {exc}")

        print("[WeldDefectPositionDetector] Warning: adaptive-image-processor.py not found, "
              "preprocessing will be skipped (accuracy may be reduced).")
        return None

    def _preprocess(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Apply adaptive preprocessing (negative + windowing + sharpening) then
        return a 3-channel BGR image suitable for YOLO inference.

        This matches the training-time preprocessing used in
        21_inference_yolo_detection.py.

        Args:
            image_bgr: Input image as numpy array in BGR format.

        Returns:
            Preprocessed image in BGR format (H × W × 3, uint8).
        """
        if self.processor is None:
            return image_bgr

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        processed_gray = self.processor.process_image(gray_bgr)

        # Adaptive sharpening
        blurred = cv2.GaussianBlur(processed_gray, (0, 0), sigmaX=2.0)
        local_contrast = processed_gray.astype(np.float32) - blurred.astype(np.float32)
        local_std = cv2.GaussianBlur(
            (local_contrast ** 2).astype(np.float32), (0, 0), sigmaX=10.0
        ) ** 0.5
        gain = 1.0 + 0.5 * (local_std / (local_std.max() + 1e-6))
        sharpened = np.clip(
            processed_gray.astype(np.float32) + gain * local_contrast, 0, 255
        ).astype(np.uint8)

        return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)


    def _calculate_origin(self, detections: List[Dict]):
        """
        Calculate origin (x, y), positioning_type, and origin_text from raw detections.
        Logic: Prioritize center_mark (ID 0), then left_marks (ID 1, 3).
               Ignore right marks.

        Returns:
            (origin_x, origin_y, positioning_type, origin_text) — each may be None.
            origin_text is always None as OCR is removed.
        """
        # 1. Check center mark
        center_marks = [d for d in detections if d['class_id'] == 0]
        if center_marks:
            best = max(center_marks, key=lambda x: x['confidence'])
            return best['center_x'], best['center_y'], 0, None

        # 2. Check left marks (1: letter_left, 3: number_left)
        left_marks = [d for d in detections if d['class_id'] in [1, 3]]
        if left_marks:
            best_left = max(left_marks, key=lambda x: x['confidence'])
            return best_left['center_x'], best_left['center_y'], 1, None

        return None, None, None, None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, image_bgr: np.ndarray) -> Dict:
        """
        Run weld defect position detection on a corrected BGR image.

        Args:
            image_bgr: Input image as numpy array in BGR format (corrected
                       original, before any windowing).

        Returns:
            Result dict::

                {
                    "detected":         bool,
                    "positioning_type": int | None,
                    "origin_x":         float | None,
                    "origin_y":         float | None,
                    "detections":       [ {...}, ... ]
                }
        """
        preprocessed = self._preprocess(image_bgr)
        results_all = self.model(preprocessed, conf=self.conf_threshold, verbose=False)
        result = results_all[0]

        if len(result.boxes) == 0:
            return {
                'detected': False,
                'positioning_type': None,
                'origin_x': None,
                'origin_y': None,
                'detections': [],
            }

        detections: List[Dict] = []
        for i in range(len(result.boxes)):
            class_id = int(result.boxes.cls[i])
            conf     = float(result.boxes.conf[i])
            bbox     = result.boxes.xyxy[i].cpu().numpy().tolist()

            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2

            detections.append({
                'class_id':   class_id,
                'class_name': _CLASS_NAMES[class_id] if class_id < len(_CLASS_NAMES) else str(class_id),
                'confidence': conf,
                'bbox':       [int(v) for v in bbox],
                'center_x':   float(center_x),
                'center_y':   float(center_y),
                'text':       None,
            })

        origin_x, origin_y, positioning_type, origin_text = self._calculate_origin(detections)

        return {
            'detected':         origin_x is not None,
            'positioning_type': positioning_type,
            'origin_x':         origin_x,
            'origin_y':         origin_y,
            'origin_text':      origin_text,
            'detections':       detections,
        }


# ---------------------------------------------------------------------------
# Factory and convenience functions
# ---------------------------------------------------------------------------

def create_detector(model_path: Union[str, Path, None] = None) -> WeldDefectPositionDetector:
    """
    Factory function to create a WeldDefectPositionDetector instance.
    """
    if model_path is None:
        model_path = DEFAULT_LOCATION1_MODEL_PATH
    return WeldDefectPositionDetector(model_path=str(model_path))


def detect_defect_position(image_bgr: np.ndarray,
                           model_path: Union[str, Path, None] = None,
                           conf_threshold: float = 0.25) -> Dict:
    """
    Convenience function to run defect position detection on a single image.
    """
    detector = create_detector(
        model_path=model_path, 
        conf_threshold=conf_threshold
    )
    return detector.predict(image_bgr)


def compute_grayscale_density(image_bgr: np.ndarray,
                              region_w: int = 20,
                              region_h: int = 50) -> Optional[str]:
    """
    Compute grayscale density (film density) for a linear weld image.

    Samples three 20x50 px regions at horizontal positions:
        (x*20%, y/2),  (x/2, y/2),  (x*80%, y/2)

    Args:
        image_bgr: Input BGR image (corrected original).
        region_w: Width of the sampling region in pixels (default 20).
        region_h: Height of the sampling region in pixels (default 50).

    Returns:
        A string formatted as "min-max" (e.g. "38-210"), or None if
        the image is invalid or regions cannot be sampled.
    """
    if image_bgr is None or image_bgr.size == 0:
        return None

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    h, w = gray.shape[:2]

    half_w = region_w // 2
    half_h = region_h // 2

    patches = []
    cy = h / 2.0
    for frac in (0.2, 0.5, 0.8):
        cx = w * frac
        x1 = max(0, int(cx) - half_w)
        y1 = max(0, int(cy) - half_h)
        x2 = min(w, x1 + region_w)
        y2 = min(h, y1 + region_h)
        if x2 > x1 and y2 > y1:
            patches.append(gray[y1:y2, x1:x2])

    if not patches:
        return None

    all_vals = np.concatenate([p.flatten() for p in patches])
    g_min = int(np.min(all_vals))
    g_max = int(np.max(all_vals))
    return f"{g_min}-{g_max}"
