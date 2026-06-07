#!/usr/bin/env python3
"""Structured logging setup for IQI pipeline."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON-lines formatter for machine-parseable logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("stage", "image", "elapsed_ms", "result_code",
                     "wire_count", "plate_code", "error", "candidates",
                     "iqi_type", "grade"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO, json_output: bool = True) -> None:
    root = logging.getLogger("gauge")
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            StructuredFormatter()
            if json_output
            else logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)
    for name in ("ultralytics", "paddleocr", "paddle", "matplotlib", "PIL"):
        logging.getLogger(name).setLevel(logging.WARNING)
