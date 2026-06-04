#!/usr/bin/env python3
"""Shared normalized-SNR service for frontend-selected image regions."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import cv2
import numpy as np


class RegionSNRService:
    """Compute measured and normalized SNR on a cropped image region."""

    RESULT_TABLE = {
        0: ("ok", "计算成功"),
        4001: ("region_area_invalid", "输入区域面积必须不小于 20 像素 × 55 像素"),
        4002: ("gray_std_zero", "输入区域灰度标准差为 0，无法计算信噪比"),
    }

    def __init__(
        self,
        sr_b_um: float = 88.6,
        max_region_area_px: int = 20 * 55,
    ):
        self.sr_b_um = float(sr_b_um)
        self.max_region_area_px = int(max_region_area_px)
        if self.sr_b_um <= 0:
            raise ValueError("sr_b_um must be > 0")
        if self.max_region_area_px <= 0:
            raise ValueError("max_region_area_px must be > 0")

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @classmethod
    def _build_status(cls, result_code: int, message: Optional[str] = None) -> Dict[str, Any]:
        result_code = int(result_code)
        result_name, default_message = cls.RESULT_TABLE.get(result_code, ("unknown_error", "未知错误"))
        return {
            "ok": result_code == 0,
            "status": "ok" if result_code == 0 else "error",
            "result_code": result_code,
            "result_name": result_name,
            "message": str(message or default_message),
        }

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            return image
        if image.ndim == 3 and image.shape[2] == 1:
            return image[:, :, 0]
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def _build_payload(
        self,
        result_code: int,
        *,
        width: int,
        height: int,
        area_pixels: int,
        gray_mean: Optional[float],
        gray_std: Optional[float],
        snr_m: Optional[float],
        snr_n: Optional[float],
        timings_ms: Dict[str, float],
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            **self._build_status(result_code, message=message),
            "snr_m": None if snr_m is None else float(snr_m),
            "snr_n": None if snr_n is None else float(snr_n),
            "sr_b_um": float(self.sr_b_um),
            "gray_mean": None if gray_mean is None else float(gray_mean),
            "gray_std": None if gray_std is None else float(gray_std),
            "width": int(width),
            "height": int(height),
            "area_pixels": int(area_pixels),
            "area_limit_pixels": int(self.max_region_area_px),
            "timings_ms": {str(k): round(float(v), 3) for k, v in timings_ms.items()},
        }
        return payload

    def compute_image(self, image: np.ndarray) -> Dict[str, Any]:
        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("输入图像为空")

        total_start = time.perf_counter()

        gray_start = time.perf_counter()
        gray = self._to_gray(image)
        gray_ms = (time.perf_counter() - gray_start) * 1000.0

        height, width = int(gray.shape[0]), int(gray.shape[1])
        area_pixels = int(width * height)

        if area_pixels < self.max_region_area_px:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            return self._build_payload(
                4001,
                width=width,
                height=height,
                area_pixels=area_pixels,
                gray_mean=None,
                gray_std=None,
                snr_m=None,
                snr_n=None,
                message=(
                    "输入区域面积必须不小于 20 像素 × 55 像素，"
                    f"当前区域为 {width} × {height} 像素（面积 {area_pixels}）"
                ),
                timings_ms={
                    "gray_ms": gray_ms,
                    "stats_ms": 0.0,
                    "snr_ms": 0.0,
                    "total_ms": total_ms,
                },
            )

        stats_start = time.perf_counter()
        gray_float = gray.astype(np.float32, copy=False)
        gray_mean = float(np.mean(gray_float))
        gray_std = float(np.std(gray_float))
        stats_ms = (time.perf_counter() - stats_start) * 1000.0

        if gray_std <= 1e-12:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            return self._build_payload(
                4002,
                width=width,
                height=height,
                area_pixels=area_pixels,
                gray_mean=gray_mean,
                gray_std=gray_std,
                snr_m=None,
                snr_n=None,
                timings_ms={
                    "gray_ms": gray_ms,
                    "stats_ms": stats_ms,
                    "snr_ms": 0.0,
                    "total_ms": total_ms,
                },
            )

        snr_start = time.perf_counter()
        snr_m = gray_mean / gray_std
        snr_n = snr_m * 88.6 / self.sr_b_um
        snr_ms = (time.perf_counter() - snr_start) * 1000.0
        total_ms = (time.perf_counter() - total_start) * 1000.0

        return self._build_payload(
            0,
            width=width,
            height=height,
            area_pixels=area_pixels,
            gray_mean=gray_mean,
            gray_std=gray_std,
            snr_m=snr_m,
            snr_n=snr_n,
            timings_ms={
                "gray_ms": gray_ms,
                "stats_ms": stats_ms,
                "snr_ms": snr_ms,
                "total_ms": total_ms,
            },
        )
