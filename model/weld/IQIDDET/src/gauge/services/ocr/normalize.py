#!/usr/bin/env python3
"""OCR output normalization helpers."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _unwrap_result(raw_output: Any) -> Any:
    result = raw_output
    if isinstance(result, list):
        if not result:
            return None
        if len(result) == 1:
            result = result[0]
    if hasattr(result, "keys") and "res" in result and isinstance(result.get("res"), dict):
        return result.get("res")
    return result


def _to_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _first_value(value: Any) -> Any:
    current = value
    while isinstance(current, (list, tuple)):
        if not current:
            return None
        current = current[0]
    if isinstance(current, np.ndarray):
        if current.size == 0:
            return None
        if current.ndim == 0:
            return current.item()
        return current.reshape(-1)[0].item()
    if isinstance(current, np.generic):
        return current.item()
    return current


def normalize_text_det_output(result: Any) -> Dict[str, Any]:
    result = _unwrap_result(result)
    if result is None:
        return {"dt_polys": [], "dt_scores": []}
    if hasattr(result, "keys"):
        dt_polys = result.get("dt_polys")
        dt_scores = result.get("dt_scores")
        return {
            "dt_polys": _to_list(dt_polys),
            "dt_scores": _to_list(dt_scores),
        }
    return {"dt_polys": [], "dt_scores": []}


def normalize_text_rec_output(result: Any) -> Dict[str, Any]:
    result = _unwrap_result(result)
    if result is None or not hasattr(result, "keys"):
        return {"rec_text": "", "rec_score": None}

    rec_text = _first_value(result.get("rec_text"))
    rec_score = _first_value(result.get("rec_score"))
    text_value = "" if rec_text is None else str(rec_text)
    score_value = None if rec_score is None else float(rec_score)
    return {
        "rec_text": text_value,
        "rec_score": score_value,
    }


def _normalize_text(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def _contains_jb(text: str) -> bool:
    return "J" in _normalize_text(text)


def _filter_items_with_jb(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in items if _contains_jb(item.get("text", ""))]
