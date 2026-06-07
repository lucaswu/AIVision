#!/usr/bin/env python3
"""FastAPI-friendly wrapper for frontend-selected text-region OCR."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import numpy as np

from gauge.runtime.region_runtime import decode_base64, executor, register_region_service_shutdown
from gauge.services.region.ocr_service import RegionOCRService

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


class RecognizeRequest(BaseModel):
    image_base64: str = Field(..., description="前端框选后的区域图像，base64 编码，支持 data URL 前缀。")


class RecognizeResponse(BaseModel):
    status: str = Field(..., description="识别状态，ok / empty")
    text: str = Field(..., description="原始识别结果")
    normalized_text: str = Field(..., description="大写字母数字标准化结果")
    score: Optional[float] = Field(default=None, description="识别置信度")
    width: int = Field(..., description="输入区域宽度")
    height: int = Field(..., description="输入区域高度")
    preprocess_mode: str = Field(..., description="识别前预处理模式")
    orientation: Dict[str, Any] = Field(..., description="文本矫正模型输出")
    timings_ms: Dict[str, float] = Field(..., description="各子阶段耗时")


_region_ocr_service: Optional[RegionOCRService] = None


def init_region_ocr_api(
    ocr_rec_model_dir: str = "models/OCR_rec_inference_best_accuracy",
    ocr_rec_model_name: str = "en_PP-OCRv5_mobile_rec",
    ocr_device: str = "gpu",
    enhance_mode: str = "windowing",
    enable_orientation: bool = True,
    ocr_orientation_model: str = "models/ocr_orientation_model.pth",
    ocr_orientation_device: Optional[str] = None,
    ocr_orientation_verbose: bool = False,
    python_bin: Optional[str] = None,
    ocr_det_model_dir: Optional[str] = None,
    ocr_det_model_name: str = "PP-OCRv5_server_det",
    ocr_det_limit_side_len: Optional[int] = None,
    ocr_det_limit_type: Optional[str] = None,
) -> RegionOCRService:
    global _region_ocr_service
    if _region_ocr_service is not None:
        _region_ocr_service.close()
    _region_ocr_service = RegionOCRService(
        ocr_rec_model_dir=ocr_rec_model_dir,
        ocr_rec_model_name=ocr_rec_model_name,
        ocr_device=ocr_device,
        enhance_mode=enhance_mode,
        enable_orientation=enable_orientation,
        ocr_orientation_model=ocr_orientation_model,
        ocr_orientation_device=ocr_orientation_device,
        ocr_orientation_verbose=ocr_orientation_verbose,
        python_bin=python_bin,
        ocr_det_model_dir=ocr_det_model_dir,
        ocr_det_model_name=ocr_det_model_name,
        ocr_det_limit_side_len=ocr_det_limit_side_len,
        ocr_det_limit_type=ocr_det_limit_type,
    )
    return _region_ocr_service


def get_region_ocr_service() -> RegionOCRService:
    global _region_ocr_service
    if _region_ocr_service is None:
        _region_ocr_service = init_region_ocr_api()
    return _region_ocr_service


def close_region_ocr_api() -> None:
    global _region_ocr_service
    if _region_ocr_service is not None:
        _region_ocr_service.close()
        _region_ocr_service = None


register_region_service_shutdown(close_region_ocr_api)


def _sync_ocr_recognize(img: np.ndarray) -> Dict[str, Any]:
    service = get_region_ocr_service()
    return service.recognize_image(img)


async def recognize_region(request: RecognizeRequest) -> RecognizeResponse:
    """同步识别单张图片区域（base64 输入），用于前端实时 OCR 框选功能。"""
    img = decode_base64(request.image_base64)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(executor, _sync_ocr_recognize, img)
        return RecognizeResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"区域 OCR 识别失败: {str(exc)}")


__all__ = [
    "RecognizeRequest",
    "RecognizeResponse",
    "RegionOCRService",
    "close_region_ocr_api",
    "get_region_ocr_service",
    "init_region_ocr_api",
    "recognize_region",
]
