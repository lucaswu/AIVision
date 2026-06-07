#!/usr/bin/env python3
"""Aggregate statistics for IQI records."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def build_ocr_statistics(results: List[Dict[str, Any]], topk: int = 200) -> Dict[str, Any]:
    """Aggregate OCR-level stats across all image records."""

    def _normalize_text(text: str) -> str:
        return "".join(ch for ch in str(text).upper() if ch.isalnum())

    status_counter = Counter()
    ocr_status_counter = Counter()
    raw_text_counter = Counter()
    norm_text_counter = Counter()

    for record in results:
        status_counter[str(record.get("status", "unknown"))] += 1
        ocr = record.get("ocr") or {}
        ocr_status_counter[str(ocr.get("status", "missing"))] += 1
        for text in ocr.get("texts", []) or []:
            raw = str(text)
            norm = _normalize_text(raw)
            raw_text_counter[raw] += 1
            if norm:
                norm_text_counter[norm] += 1

    return {
        "images_total": len(results),
        "pipeline_status": {k: int(v) for k, v in status_counter.items()},
        "ocr_status": {k: int(v) for k, v in ocr_status_counter.items()},
        "top_raw_text": {k: int(v) for k, v in raw_text_counter.most_common(topk)},
        "top_normalized_text": {k: int(v) for k, v in norm_text_counter.most_common(topk)},
    }
