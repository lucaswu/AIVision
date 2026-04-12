#!/usr/bin/env python3
"""FastAPI-friendly wrapper for frontend-selected region normalized-SNR."""

from __future__ import annotations

import asyncio
import atexit
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import cv2
import numpy as np

from gauge.region_snr_service import RegionSNRService

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


class SNRRequest(BaseModel):
    image_base64: str = Field(..., description="前端框选后的区域图像，base64 编码，支持 data URL 前缀。")


class SNRResponse(BaseModel):
    ok: bool = Field(..., description="是否计算成功。")
    status: str = Field(..., description="计算状态，ok / error。")
    result_code: int = Field(..., description="结果码，0 表示成功。")
    result_name: str = Field(..., description="结果码名称。")
    message: str = Field(..., description="结果说明。")
    snr_m: Optional[float] = Field(default=None, description="测量信噪比 SNR_m。")
    snr_n: Optional[float] = Field(default=None, description="归一化信噪比 SNR_n。")
    sr_b_um: float = Field(..., description="分辨力 SR_b，单位微米。")
    gray_mean: Optional[float] = Field(default=None, description="测量区域灰度均值。")
    gray_std: Optional[float] = Field(default=None, description="测量区域灰度标准差。")
    width: int = Field(..., description="输入区域宽度。")
    height: int = Field(..., description="输入区域高度。")
    area_pixels: int = Field(..., description="输入区域像素面积。")
    area_limit_pixels: int = Field(..., description="区域面积阈值（当前要求输入区域面积不小于该值）。")
    timings_ms: Dict[str, float] = Field(..., description="各子阶段耗时。")


_region_snr_service: Optional[RegionSNRService] = None
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="region-snr")


def init_region_snr_api(
    sr_b_um: float = 88.6,
    max_region_area_px: int = 20 * 55,
) -> RegionSNRService:
    global _region_snr_service
    if _region_snr_service is not None:
        _region_snr_service.close()
    _region_snr_service = RegionSNRService(
        sr_b_um=sr_b_um,
        max_region_area_px=max_region_area_px,
    )
    return _region_snr_service


def get_region_snr_service() -> RegionSNRService:
    global _region_snr_service
    if _region_snr_service is None:
        _region_snr_service = init_region_snr_api()
    return _region_snr_service


def close_region_snr_api() -> None:
    global _region_snr_service
    if _region_snr_service is not None:
        _region_snr_service.close()
        _region_snr_service = None


def _shutdown_executor() -> None:
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:  # pragma: no cover
        executor.shutdown(wait=False)


atexit.register(close_region_snr_api)
atexit.register(_shutdown_executor)


def _decode_base64_image(image_base64: str) -> np.ndarray:
    b64_data = str(image_base64 or "")
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(b64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="无法解码图片")
        return img
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"图片解码失败: {str(exc)}")


def _sync_compute_region_snr(img: np.ndarray) -> Dict[str, Any]:
    service = get_region_snr_service()
    return service.compute_image(img)


async def compute_region_snr(request: SNRRequest) -> SNRResponse:
    """计算单个区域的归一化信噪比（base64 输入）。"""
    img = _decode_base64_image(request.image_base64)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(executor, _sync_compute_region_snr, img)
        return SNRResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"区域归一化信噪比计算失败: {str(exc)}")


__all__ = [
    "SNRRequest",
    "SNRResponse",
    "RegionSNRService",
    "close_region_snr_api",
    "compute_region_snr",
    "get_region_snr_service",
    "init_region_snr_api",
]
