#!/usr/bin/env python3
"""Shared runtime utilities for region OCR and SNR APIs."""

from __future__ import annotations

import atexit
import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List

import cv2
import numpy as np

try:
    from fastapi import HTTPException
except ImportError:
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = int(status_code)
            self.detail = str(detail)


executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="region-svc")
_shutdown_callbacks: List[Callable[[], None]] = []


def decode_base64(image_base64: str) -> np.ndarray:
    b64_data = str(image_base64 or "")
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(b64_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="无法解码图片") from exc
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="无法解码图片")
    return img


def register_region_service_shutdown(callback: Callable[[], None]) -> None:
    _shutdown_callbacks.append(callback)


def shutdown_region_runtime() -> None:
    while _shutdown_callbacks:
        callback = _shutdown_callbacks.pop()
        try:
            callback()
        except Exception:
            pass
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        executor.shutdown(wait=False)


atexit.register(shutdown_region_runtime)
