#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weld Defect Position Detection Utility (Location 1)

This module provides functionality to detect defect positions (origin / mark
positions) in corrected weld film images using a YOLO detection model
(location_1.pt) combined with PaddleOCR.

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

try:
    from paddleocr import PaddleOCR
    HAS_PADDLEOCR = True
except ImportError:
    HAS_PADDLEOCR = False

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
    Weld defect position detector using a YOLO detection model + PaddleOCR.

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
            "origin_text":       str | None,   # OCR text of chosen edge mark; None for center_mark
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
                 use_ocr: bool = True,
                 adaptive_processor_path: Optional[str] = None):
        """
        Initialize the weld defect position detector.

        Args:
            model_path: Path to the YOLO detection model weights (.pt file).
            conf_threshold: Minimum confidence to keep a detection.
            use_ocr: Whether to run PaddleOCR on detected mark regions.
            adaptive_processor_path: Explicit path to adaptive-image-processor.py.
                If None, the module will search relative to the weld root and cwd.
        """
        from ultralytics import YOLO  # lazy import

        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.use_ocr = use_ocr

        # Load adaptive preprocessor
        self.processor = self._load_processor(adaptive_processor_path)

        # Load YOLO detection model
        self.model = YOLO(str(self.model_path))

        # Initialize PaddleOCR
        self.reader = None
        if self.use_ocr and HAS_PADDLEOCR:
            self.reader = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        elif self.use_ocr:
            print("[WeldDefectPositionDetector] Warning: PaddleOCR not available, OCR will be skipped.")

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

    def _extract_text_from_bbox(self, image_preprocessed: np.ndarray,
                                bbox: List[float]) -> Optional[str]:
        """
        Run PaddleOCR on the region defined by bbox in the preprocessed image.

        Args:
            image_preprocessed: Preprocessed BGR image.
            bbox: [x1, y1, x2, y2] bounding box coordinates.

        Returns:
            Best OCR text (alphanumeric, uppercase), or None.
        """
        if self.reader is None:
            return None

        x1, y1, x2, y2 = map(int, bbox)
        img_h, img_w = image_preprocessed.shape[:2]

        # Expand ROI by 50%
        pad_x = int((x2 - x1) * 0.5)
        pad_y = int((y2 - y1) * 0.5)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(img_w, x2 + pad_x)
        y2 = min(img_h, y2 + pad_y)

        roi = image_preprocessed[y1:y2, x1:x2]
        if roi.size == 0:
            return None

        try:
            ocr_result = self.reader.ocr(roi, cls=True)
            if not ocr_result or not ocr_result[0]:
                return None

            candidates = []
            for line in ocr_result[0]:
                text_raw, score = line[1][0], line[1][1]
                cleaned = ''.join(c for c in text_raw if c.isalnum()).upper()
                if cleaned:
                    candidates.append((cleaned, score))

            if not candidates:
                return None
            best_text, _ = max(candidates, key=lambda x: x[1])
            return best_text
        except Exception as exc:
            print(f"[WeldDefectPositionDetector] OCR failed: {exc}")
            return None

    def _compare_marks(self, left_value, right_value, left_type, right_type) -> str:
        """
        Compare left/right marks to determine the origin side.

        Returns:
            'left' or 'right'
        """
        if not left_value and not right_value:
            return 'left'

        if not left_value or not right_value:
            recognized_side = 'right' if not left_value else 'left'
            recognized_value = right_value if not left_value else left_value
            recognized_type = right_type if not left_value else left_type
            other_side = 'left' if recognized_side == 'right' else 'right'

            if recognized_type == 'letter':
                letter = next((c for c in recognized_value if c.isalpha()), None)
                if letter == 'A':
                    return recognized_side
                elif letter:
                    return other_side
            else:
                try:
                    num = int(''.join(c for c in recognized_value if c.isdigit()))
                    return recognized_side if num == 1 else other_side
                except ValueError:
                    pass
            return recognized_side

        if left_type != right_type:
            return 'left'

        if left_type == 'letter':
            left_letter = next((c for c in left_value if c.isalpha()), None)
            right_letter = next((c for c in right_value if c.isalpha()), None)
            if not left_letter or not right_letter:
                recognized_side = 'right' if not left_letter else 'left'
                letter = right_letter if not left_letter else left_letter
                other_side = 'left' if recognized_side == 'right' else 'right'
                return recognized_side if letter == 'A' else other_side
            return 'left' if left_letter < right_letter else 'right'
        else:
            left_digits = ''.join(c for c in left_value if c.isdigit())
            right_digits = ''.join(c for c in right_value if c.isdigit())
            if not left_digits or not right_digits:
                recognized_side = 'right' if not left_digits else 'left'
                digits = right_digits if not left_digits else left_digits
                other_side = 'left' if recognized_side == 'right' else 'right'
                try:
                    num = int(digits)
                    return recognized_side if num == 1 else other_side
                except ValueError:
                    return 'left'
            left_num, right_num = int(left_digits), int(right_digits)
            return 'left' if left_num < right_num else 'right'

    def _calculate_origin(self, detections: List[Dict]):
        """
        Calculate origin (x, y), positioning_type, and origin_text from raw detections.

        Returns:
            (origin_x, origin_y, positioning_type, origin_text)  — each may be None.
            origin_text is the OCR text of the chosen edge mark, or None for center_mark.
        """
        center_marks = [d for d in detections if d['class_id'] == 0]
        if center_marks:
            best = max(center_marks, key=lambda x: x['confidence'])
            return best['center_x'], best['center_y'], 0, None

        left_marks  = [d for d in detections if d['class_id'] in [1, 3]]
        right_marks = [d for d in detections if d['class_id'] in [2, 4]]

        if left_marks and right_marks:
            best_left  = max(left_marks,  key=lambda x: x['confidence'])
            best_right = max(right_marks, key=lambda x: x['confidence'])
            left_type  = 'letter' if best_left['class_id'] == 1 else 'number'
            right_type = 'letter' if best_right['class_id'] == 2 else 'number'
            origin_side = self._compare_marks(
                best_left['text'], best_right['text'], left_type, right_type)
            chosen = best_left if origin_side == 'left' else best_right
            return chosen['center_x'], chosen['center_y'], 1, chosen.get('text')

        if left_marks:
            best = max(left_marks, key=lambda x: x['confidence'])
            return best['center_x'], best['center_y'], 1, best.get('text')

        if right_marks:
            best = max(right_marks, key=lambda x: x['confidence'])
            return best['center_x'], best['center_y'], 1, best.get('text')

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

            # OCR on non-center marks
            text = None
            if class_id != 0:
                text = self._extract_text_from_bbox(preprocessed, bbox)

            detections.append({
                'class_id':   class_id,
                'class_name': _CLASS_NAMES[class_id] if class_id < len(_CLASS_NAMES) else str(class_id),
                'confidence': conf,
                'bbox':       [int(v) for v in bbox],
                'center_x':   float(center_x),
                'center_y':   float(center_y),
                'text':       text,
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

def create_detector(model_path: Union[str, Path, None] = None,
                    **kwargs) -> WeldDefectPositionDetector:
    """
    Factory function to create a WeldDefectPositionDetector instance.

    Args:
        model_path: Path to the YOLO detection model weights.
                    Defaults to ``weight/location_1.pt`` relative to the
                    weld module root.
        **kwargs: Additional keyword arguments forwarded to
                  :class:`WeldDefectPositionDetector`.

    Returns:
        WeldDefectPositionDetector instance.
    """
    if model_path is None:
        model_path = DEFAULT_LOCATION1_MODEL_PATH
    return WeldDefectPositionDetector(model_path=str(model_path), **kwargs)


def detect_defect_position(image_bgr: np.ndarray,
                           model_path: Union[str, Path, None] = None,
                           conf_threshold: float = 0.25) -> Dict:
    """
    Convenience function to run defect position detection on a single image.

    Args:
        image_bgr: Input BGR image (corrected original).
        model_path: Path to model weights (uses default if None).
        conf_threshold: Minimum detection confidence.

    Returns:
        Result dict (see :meth:`WeldDefectPositionDetector.predict`).
    """
    detector = create_detector(model_path=model_path, conf_threshold=conf_threshold)
    return detector.predict(image_bgr)
