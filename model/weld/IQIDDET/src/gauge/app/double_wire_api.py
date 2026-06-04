#!/usr/bin/env python3
"""FastAPI-friendly wrapper for double-wire IQI analysis."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import numpy as np

from gauge.runtime.region_runtime import decode_base64, executor, register_region_service_shutdown
from gauge.services.double_wire.service import DoubleWireService

try:  # pragma: no cover
    from fastapi import HTTPException
except ImportError:  # pragma: no cover
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = int(status_code)
            self.detail = str(detail)

try:  # pragma: no cover
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    class BaseModel:
        def __init__(self, **data: Any):
            for key, value in data.items():
                setattr(self, key, value)
        def model_dump(self) -> Dict[str, Any]:
            return dict(self.__dict__)
    def Field(default: Any = None, **_kwargs: Any) -> Any:
        return default


class DoubleWireRequest(BaseModel):
    image_base64: str = Field(
        ..., description="strip 条带图像 base64 编码，支持 data URL 前缀。",
    )


class DoubleWireResponse(BaseModel):
    ok: bool = Field(..., description="是否分析成功。")
    status: str = Field(..., description="分析状态，ok / error。")
    result_code: int = Field(..., description="结果码，0 表示成功。")
    result_name: str = Field(..., description="结果码名称。")
    message: str = Field(..., description="结果说明。")
    timings_ms: Dict[str, float] = Field(..., description="各阶段耗时。")
    strip_shape: Optional[List[int]] = Field(
        default=None, description="strip 图像尺寸 [height, width]。",
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="分析结果，见 docs/contract/DOUBLE_WIRE_ANALYSIS_API.md。",
    )


_double_wire_service: Optional[DoubleWireService] = None


def init_double_wire_api(
    min_distance: int = 5,
    prominence: float = 0.03,
) -> DoubleWireService:
    global _double_wire_service
    if _double_wire_service is not None:
        _double_wire_service.close()
    _double_wire_service = DoubleWireService(
        min_distance=min_distance, prominence=prominence,
    )
    return _double_wire_service


def get_double_wire_service() -> DoubleWireService:
    global _double_wire_service
    if _double_wire_service is None:
        _double_wire_service = init_double_wire_api()
    return _double_wire_service


def close_double_wire_api() -> None:
    global _double_wire_service
    if _double_wire_service is not None:
        _double_wire_service.close()
        _double_wire_service = None


register_region_service_shutdown(close_double_wire_api)


def _sync_compute(img: np.ndarray) -> Dict[str, Any]:
    """BGR → GRAY float64 → service.compute."""
    import cv2
    if img.ndim == 3:
        strip = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64)
    else:
        strip = img.astype(np.float64)
    service = get_double_wire_service()
    return service.compute(strip)


async def compute_double_wire(request: DoubleWireRequest) -> DoubleWireResponse:
    """分析双丝像质计 strip 图像（base64 输入）。"""
    img = decode_base64(request.image_base64)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(executor, _sync_compute, img)
        return DoubleWireResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"双丝像质计分析失败: {str(exc)}",
        )


__all__ = [
    "DoubleWireRequest",
    "DoubleWireResponse",
    "DoubleWireService",
    "close_double_wire_api",
    "compute_double_wire",
    "get_double_wire_service",
    "init_double_wire_api",
]
