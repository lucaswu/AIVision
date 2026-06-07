#!/usr/bin/env python3
"""Double-wire IQI analysis service — pure computation, no web framework."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import numpy as np

from gauge.imaging.double_wire import analyze_double_wire


class DoubleWireService:
    """Compute double-wire IQI analysis on a strip image.

    Thin wrapper around :func:`analyze_double_wire` that handles
    serialization of numpy arrays and timing instrumentation.
    """

    RESULT_TABLE = {
        0: ("ok", "分析成功"),
        5001: ("invalid_image", "图像解码失败或为空"),
        5002: ("profile_too_short", "strip 宽度 < 3，无法分析"),
        5003: ("no_extrema_found", "未检出峰或谷"),
        5999: ("internal_error", "内部异常"),
    }

    def __init__(
        self,
        min_distance: int = 5,
        prominence: float = 0.03,
    ):
        self.min_distance = int(min_distance)
        self.prominence = float(prominence)

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @classmethod
    def _build_status(cls, result_code: int, message: Optional[str] = None) -> Dict[str, Any]:
        result_name, default_message = cls.RESULT_TABLE.get(
            result_code, ("unknown_error", "未知错误"),
        )
        return {
            "ok": result_code == 0,
            "status": "ok" if result_code == 0 else "error",
            "result_code": result_code,
            "result_name": result_name,
            "message": str(message or default_message),
        }

    @staticmethod
    def _serialize_result(r) -> Dict[str, Any]:
        """Convert DoubleWireResult fields to JSON-serializable dict."""
        return {
            "film_type": r.film_type,
            "num_pairs": len(r.pairs),
            "first_unresolved_group": r.first_unresolved_group,
            "profile": r.profile.tolist(),
            "background": r.background.tolist(),
            "peaks": r.peaks,
            "valleys": r.valleys,
            "pairs": r.pairs_as_dicts(),
        }

    def compute(self, strip: np.ndarray) -> Dict[str, Any]:
        """Run analysis on a strip image.

        Args:
            strip: 2D ndarray of shape (band_height, num_samples).

        Returns:
            Dict matching the DOUBLE_WIRE_ANALYSIS_API contract.
        """
        if strip is None or not isinstance(strip, np.ndarray) or strip.size == 0:
            return {
                **self._build_status(5001, message="输入图像为空"),
                "timings_ms": {"total_ms": 0.0},
                "strip_shape": None,
                "result": None,
            }

        total_start = time.perf_counter()

        try:
            r = analyze_double_wire(
                strip,
                min_distance=self.min_distance,
                prominence=self.prominence,
            )
        except Exception as exc:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            return {
                **self._build_status(5999, message=str(exc)),
                "timings_ms": {"total_ms": round(total_ms, 3)},
                "strip_shape": list(strip.shape) if strip.ndim == 2 else None,
                "result": None,
            }

        total_ms = (time.perf_counter() - total_start) * 1000.0

        if len(r.profile) < 3:
            return {
                **self._build_status(
                    5002, message=f"strip 宽度 = {len(r.profile)}，无法分析",
                ),
                "timings_ms": {"total_ms": round(total_ms, 3)},
                "strip_shape": list(r.strip_shape),
                "result": None,
            }

        if len(r.peaks) == 0 and len(r.valleys) == 0:
            return {
                **self._build_status(5003, message="未检出峰或谷"),
                "timings_ms": {"total_ms": round(total_ms, 3)},
                "strip_shape": list(r.strip_shape),
                "result": self._serialize_result(r),
            }

        return {
            **self._build_status(0),
            "timings_ms": {"total_ms": round(total_ms, 3)},
            "strip_shape": list(r.strip_shape),
            "result": self._serialize_result(r),
        }
