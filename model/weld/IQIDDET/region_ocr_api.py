#!/usr/bin/env python3
"""Root-level import facade for the region OCR API."""

from gauge.region_ocr_api import (
    RecognizeRequest,
    RecognizeResponse,
    close_region_ocr_api,
    get_region_ocr_service,
    init_region_ocr_api,
    recognize_region,
)
from gauge.region_ocr_service import RegionOCRService

__all__ = [
    "RecognizeRequest",
    "RecognizeResponse",
    "RegionOCRService",
    "close_region_ocr_api",
    "get_region_ocr_service",
    "init_region_ocr_api",
    "recognize_region",
]
