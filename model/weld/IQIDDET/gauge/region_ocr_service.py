#!/usr/bin/env python3
"""Shared text-region OCR service for frontend-selected crops."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from gauge.iqi_rules import normalize_text
from gauge.ocr_stage import PaddleOCRSubprocessClient
from gauge.pipeline_utils import enhance_windowing_gray, to_gray


class RegionOCRService:
    """Run enhancement + orientation correction + OCR on a user-selected text crop."""

    def __init__(
        self,
        ocr_rec_model_dir: str = "models/OCR_rec_inference_best_accuracy",
        ocr_rec_model_name: str = "en_PP-OCRv5_mobile_rec",
        ocr_device: str = "gpu",
        enhance_mode: str = "windowing",
        enable_orientation: bool = True,
        ocr_orientation_model: str = "models/ocr_orientation_model.pth",
        ocr_orientation_device: Optional[str] = None,
        ocr_orientation_verbose: bool = False,
        python_bin: Optional[str] = None,
    ):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.enhance_mode = str(enhance_mode)
        self.ocr_orientation_verbose = bool(ocr_orientation_verbose)
        self._infer_lock = threading.Lock()
        self.ocr_backend = PaddleOCRSubprocessClient(
            device=ocr_device,
            det_model_name="PP-OCRv5_server_det",
            rec_model_name=ocr_rec_model_name,
            rec_model_dir=str(self._resolve_path(ocr_rec_model_dir)),
            python_bin=python_bin or sys.executable,
        )
        self.ocr_text_corrector = None
        if enable_orientation:
            from gauge.ocr_orientation import OCRTextOrientationCorrector

            self.ocr_text_corrector = OCRTextOrientationCorrector(
                model_path=self._resolve_path(ocr_orientation_model),
                model_type="resnet34",
                device=ocr_orientation_device,
            )

    def _resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = (self.repo_root / path).resolve()
        return path

    def close(self) -> None:
        if self.ocr_backend is not None:
            self.ocr_backend.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def recognize_image(self, image: np.ndarray) -> Dict[str, Any]:
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("输入图像为空")

        with self._infer_lock:
            total_start = time.perf_counter()
            preprocess_start = time.perf_counter()
            if self.enhance_mode == "windowing":
                prepared = enhance_windowing_gray(image)
            elif self.enhance_mode == "gray":
                prepared = to_gray(image)
            else:
                prepared = image.copy()
            preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0

            orientation_info = {
                "label": None,
                "confidence": None,
                "status": "disabled" if self.ocr_text_corrector is None else "unknown",
                "corrected": False,
                "actions": None,
            }
            rec_image = prepared
            orientation_ms = 0.0
            if self.ocr_text_corrector is not None:
                orientation_start = time.perf_counter()
                rec_image, orientation_info = self.ocr_text_corrector.correct_image(
                    prepared,
                    verbose=self.ocr_orientation_verbose,
                )
                orientation_ms = (time.perf_counter() - orientation_start) * 1000.0

            recognize_start = time.perf_counter()
            rec_result = self.ocr_backend.recognize(rec_image)
            recognition_ms = (time.perf_counter() - recognize_start) * 1000.0

            text = str(rec_result.get("rec_text") or "")
            score = rec_result.get("rec_score")
            status = "ok" if text else "empty"
            total_ms = (time.perf_counter() - total_start) * 1000.0

            return {
                "status": status,
                "text": text,
                "normalized_text": normalize_text(text),
                "score": None if score is None else float(score),
                "width": int(image.shape[1]),
                "height": int(image.shape[0]),
                "preprocess_mode": self.enhance_mode,
                "orientation": orientation_info,
                "timings_ms": {
                    "preprocess_ms": round(float(preprocess_ms), 3),
                    "orientation_ms": round(float(orientation_ms), 3),
                    "recognition_ms": round(float(recognition_ms), 3),
                    "total_ms": round(float(total_ms), 3),
                },
            }
