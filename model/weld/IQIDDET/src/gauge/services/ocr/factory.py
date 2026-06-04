#!/usr/bin/env python3
"""PaddleOCR component construction."""

from __future__ import annotations

import inspect
import os
from typing import Any, Dict, List, Optional

import cv2
import numpy as np


def _configure_paddle_runtime(device: str) -> str:
    device = str(device).lower()
    if device not in {"cpu", "gpu"}:
        device = "cpu"
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

    try:
        import paddle

        paddle.set_device("gpu" if device == "gpu" else "cpu")
    except Exception:
        pass
    return device


def _create_paddle_component(
    component_cls,
    device: str,
    model_name: Optional[str] = None,
    model_dir: Optional[str] = None,
    **extra_init_args: Any,
):
    device = _configure_paddle_runtime(device)

    try:
        sig = inspect.signature(component_cls.__init__)
        accepted = {k for k in sig.parameters.keys() if k != "self"}
        has_var_keyword = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values())
    except Exception:
        accepted = set()
        has_var_keyword = True

    def accepts(name: str) -> bool:
        return has_var_keyword or not accepted or name in accepted

    kwargs: Dict[str, Any] = {}
    if accepts("device"):
        kwargs["device"] = device
    if model_name and accepts("model_name"):
        kwargs["model_name"] = model_name
    if model_dir and accepts("model_dir"):
        kwargs["model_dir"] = model_dir
    for key, value in extra_init_args.items():
        if value is None:
            continue
        if accepts(key):
            kwargs[key] = value
    return component_cls(**kwargs)


def create_paddle_ocr(
    lang: str = "en",
    device: str = "gpu",
    rec_model_name: str = "en_PP-OCRv5_mobile_rec",
    rec_model_dir: Optional[str] = None,
):
    """Create PaddleOCR engine and pin the recognition model when possible."""
    device = _configure_paddle_runtime(device)

    from paddleocr import PaddleOCR

    common_kwargs = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": True,
    }

    try:
        sig = inspect.signature(PaddleOCR.__init__)
        accepted = {k for k in sig.parameters.keys() if k != "self"}
        has_var_keyword = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values())
    except Exception:
        accepted = set()
        has_var_keyword = True

    def accepts(name: str) -> bool:
        return has_var_keyword or not accepted or name in accepted

    if accepts("lang"):
        common_kwargs["lang"] = lang
    if accepts("device"):
        common_kwargs["device"] = device

    candidate_kwargs: List[Dict[str, Any]] = []

    primary_kwargs = dict(common_kwargs)
    if rec_model_name and accepts("text_recognition_model_name"):
        primary_kwargs["text_recognition_model_name"] = rec_model_name
    if rec_model_dir:
        if accepts("text_recognition_model_dir"):
            primary_kwargs["text_recognition_model_dir"] = rec_model_dir
        elif accepts("rec_model_dir"):
            primary_kwargs["rec_model_dir"] = rec_model_dir
    candidate_kwargs.append(primary_kwargs)

    if rec_model_dir and "text_recognition_model_name" in primary_kwargs:
        dir_only_kwargs = dict(primary_kwargs)
        dir_only_kwargs.pop("text_recognition_model_name", None)
        candidate_kwargs.append(dir_only_kwargs)

    candidate_kwargs.append(dict(common_kwargs))
    candidate_kwargs.append(
        {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": True,
        }
    )
    candidate_kwargs.append({})

    seen = set()
    for kwargs in candidate_kwargs:
        key = tuple(sorted(kwargs.items()))
        if key in seen:
            continue
        seen.add(key)
        try:
            return PaddleOCR(**kwargs)
        except Exception:
            continue

    return PaddleOCR()


def create_text_detector(
    model_name: str = "PP-OCRv5_server_det",
    model_dir: Optional[str] = None,
    device: str = "gpu",
    limit_side_len: Optional[int] = None,
    limit_type: Optional[str] = None,
):
    from paddleocr import TextDetection

    return _create_paddle_component(
        TextDetection,
        device=device,
        model_name=model_name,
        model_dir=model_dir,
        limit_side_len=limit_side_len,
        limit_type=limit_type,
    )


def create_text_recognizer(
    model_name: str = "en_PP-OCRv5_mobile_rec",
    model_dir: Optional[str] = None,
    device: str = "gpu",
):
    from paddleocr import TextRecognition

    return _create_paddle_component(
        TextRecognition,
        device=device,
        model_name=model_name,
        model_dir=model_dir,
    )


def _ensure_rgb(image: Any) -> Any:
    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        if image.ndim == 3 and image.shape[2] == 1:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        if image.ndim == 3 and image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image
