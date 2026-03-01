#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weld Seam Location Detection Utility

This module provides functionality to detect the weld seam position in
corrected weld film images using a YOLO pose model (location_0.pt).

The model predicts up to 12 keypoints on the weld seam and supports two
detection classes:
  - 'ellipse'  : elliptical / curved weld seam
  - 'vertical' : straight / vertical weld seam

Pre-processing mirrors the training pipeline:
    AdaptiveImageProcessor(use_negative=True) → negative + windowing on BGR image.
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
DEFAULT_LOCATION_MODEL_PATH = str(_WELD_ROOT / "weight" / "location_0.pt")


class WeldSeamLocator:
    """
    Weld seam position detector using a YOLO pose model.

    Input : color BGR image (corrected original, as returned by
            WeldOrientationCorrector).
    Pre-processing: AdaptiveImageProcessor(use_negative=True) – identical
            to the training pipeline.
    Output: list of detection dicts, each containing class name, bounding
            box, confidence score and visible keypoints.

    Detection dict schema::

        {
            "class":      str,            # 'ellipse' | 'vertical'
            "confidence": float,
            "bbox":       [x1, y1, x2, y2],   # int pixels
            "keypoints":  [
                {"id": 1..12, "x": float, "y": float}  # visible pts only
            ]
        }
    """

    def __init__(self,
                 model_path: Union[str, Path] = DEFAULT_LOCATION_MODEL_PATH,
                 conf_threshold: float = 0.6,
                 adaptive_processor_path: Optional[str] = None):
        """
        Initialize the weld seam locator.

        Args:
            model_path: Path to the YOLO pose model weights (.pt file).
            conf_threshold: Minimum confidence to keep a detection.
            adaptive_processor_path: Explicit path to adaptive-image-processor.py.
                If None, the module will search relative to the weld root and cwd.
        """
        from ultralytics import YOLO  # lazy – avoids top-level 'ultralytics' dep

        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold

        # Load adaptive preprocessor (negative + windowing)
        self.processor = self._load_processor(adaptive_processor_path)

        # Load YOLO pose model
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
        # Sibling of model/weld/utils/ → model/weld/
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
                    print(f"[WeldSeamLocator] AdaptiveImageProcessor loaded: {path}")
                    return processor
                except Exception as exc:
                    print(f"[WeldSeamLocator] Warning: cannot load processor "
                          f"({path}): {exc}")

        print("[WeldSeamLocator] Warning: adaptive-image-processor.py not found, "
              "preprocessing will be skipped (accuracy may be reduced).")
        return None

    def _preprocess(self, image_bgr: np.ndarray) -> np.ndarray:
        """
        Apply adaptive preprocessing (negative + windowing) then return a
        3-channel BGR image suitable for YOLO inference.

        This exactly matches the training-time preprocessing pipeline.

        Args:
            image_bgr: Input image as numpy array in BGR format.

        Returns:
            Preprocessed image in BGR format (H × W × 3, uint8).
        """
        if self.processor is not None:
            processed = self.processor.process_image(image_bgr)
        else:
            processed = image_bgr

        # Ensure output is 3-channel BGR
        if len(processed.shape) == 2:
            processed = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)

        return processed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, image_bgr: np.ndarray) -> List[Dict]:
        """
        Run weld seam location detection on a corrected BGR image.

        For 'vertical' class detections the x-coordinates of all visible
        keypoints are averaged and straightened to the mean x, mirroring the
        behaviour of the original ``location_0_predict.py`` script.

        Args:
            image_bgr: Input image as numpy array in BGR format (corrected
                       original, before any windowing).

        Returns:
            List of detection dicts (may be empty if nothing is detected)::

                [
                    {
                        "class":      "ellipse",
                        "confidence": 0.92,
                        "bbox":       [x1, y1, x2, y2],
                        "keypoints":  [{"id": 1, "x": 123.4, "y": 56.7}, ...]
                    },
                    ...
                ]
        """
        preprocessed = self._preprocess(image_bgr)
        results_all = self.model.predict(
            preprocessed,
            conf=self.conf_threshold,
            verbose=False
        )[0]

        detections: List[Dict] = []

        if results_all.boxes is None or len(results_all.boxes) == 0:
            return detections

        names = self.model.names
        for box, kps, cls_id in zip(
                results_all.boxes,
                results_all.keypoints,
                results_all.boxes.cls):

            class_name = names[int(cls_id)]
            pts = kps.xy[0].cpu().numpy()   # shape (12, 2)

            # Vertical weld: align all visible keypoints to the mean x
            if class_name == 'vertical':
                valid = pts[pts[:, 0] > 0]
                if len(valid) > 0:
                    cx = float(np.mean(valid[:, 0]))
                    mask = pts[:, 0] > 0
                    pts[mask, 0] = cx

            keypoints = [
                {"id": i + 1, "x": float(px), "y": float(py)}
                for i, (px, py) in enumerate(pts)
                if px > 1 and py > 1   # visible keypoints only
            ]

            detections.append({
                "class":      class_name,
                "confidence": float(box.conf[0]),
                "bbox":       [int(v) for v in box.xyxy[0].tolist()],
                "keypoints":  keypoints,
            })

        return detections


# ---------------------------------------------------------------------------
# Factory and convenience functions
# ---------------------------------------------------------------------------

def create_locator(model_path: Union[str, Path, None] = None,
                   **kwargs) -> WeldSeamLocator:
    """
    Factory function to create a WeldSeamLocator instance.

    Args:
        model_path: Path to the YOLO pose model weights.
                    Defaults to ``weight/location_0.pt`` relative to the
                    weld module root.
        **kwargs: Additional keyword arguments forwarded to
                  :class:`WeldSeamLocator`.

    Returns:
        WeldSeamLocator instance.
    """
    if model_path is None:
        model_path = DEFAULT_LOCATION_MODEL_PATH
    return WeldSeamLocator(model_path=str(model_path), **kwargs)


def locate_weld_seam(image_bgr: np.ndarray,
                     model_path: Union[str, Path, None] = None,
                     conf_threshold: float = 0.6) -> List[Dict]:
    """
    Convenience function to run weld seam location on a single image.

    Args:
        image_bgr: Input BGR image (corrected original).
        model_path: Path to model weights (uses default if None).
        conf_threshold: Minimum detection confidence.

    Returns:
        List of detection dicts (see :meth:`WeldSeamLocator.predict`).
    """
    locator = create_locator(model_path=model_path, conf_threshold=conf_threshold)
    return locator.predict(image_bgr)
