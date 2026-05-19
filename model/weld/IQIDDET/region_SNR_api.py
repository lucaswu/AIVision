#!/usr/bin/env python3
"""Root-level import facade for the region normalized-SNR API."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from gauge.region_snr_api import (
    SNRRequest,
    SNRResponse,
    close_region_snr_api,
    compute_region_snr,
    get_region_snr_service,
    init_region_snr_api,
)
from gauge.region_snr_service import RegionSNRService

__all__ = [
    "SNRRequest",
    "SNRResponse",
    "RegionSNRService",
    "close_region_snr_api",
    "compute_region_snr",
    "get_region_snr_service",
    "init_region_snr_api",
]
