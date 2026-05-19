#!/usr/bin/env python3
"""Root-level import facade for the region OCR API."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

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
