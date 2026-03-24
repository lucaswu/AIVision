#!/usr/bin/env python3
"""Persistent PaddleOCR worker used by the main torch pipeline."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict

import cv2
import numpy as np

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gauge.ocr_stage import (  # noqa: E402
    _ensure_rgb,
    _run_text_det_predict,
    _run_text_rec_predict,
    create_text_detector,
    create_text_recognizer,
    normalize_text_det_output,
    normalize_text_rec_output,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PaddleOCR subprocess worker.")
    parser.add_argument("--device", default="gpu")
    parser.add_argument("--det-model-name", default="PP-OCRv5_server_det")
    parser.add_argument("--det-model-dir")
    parser.add_argument("--rec-model-name", default="en_PP-OCRv5_mobile_rec")
    parser.add_argument("--rec-model-dir")
    parser.add_argument("--det-limit-side-len", type=int)
    parser.add_argument("--det-limit-type")
    return parser.parse_args()


def decode_image(payload: Dict[str, Any]) -> np.ndarray:
    data = base64.b64decode(str(payload.get("data", "")))
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Failed to decode input image payload.")
    return image


def write_response(stream, payload: Dict[str, Any]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def main() -> None:
    args = parse_args()
    protocol_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        text_detector = create_text_detector(
            model_name=args.det_model_name,
            model_dir=args.det_model_dir,
            device=args.device,
            limit_side_len=args.det_limit_side_len,
            limit_type=args.det_limit_type,
        )
        text_recognizer = create_text_recognizer(
            model_name=args.rec_model_name,
            model_dir=args.rec_model_dir,
            device=args.device,
        )
        write_response(protocol_stdout, {"ok": True, "event": "ready"})
    except Exception as exc:
        write_response(protocol_stdout, {"ok": False, "event": "startup_error", "error": str(exc)})
        raise

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            op = str(request.get("op", ""))
            if op == "close":
                write_response(protocol_stdout, {"ok": True, "event": "closing"})
                break
            image = decode_image(request.get("image") or {})
            if op == "detect":
                result = normalize_text_det_output(_run_text_det_predict(text_detector, _ensure_rgb(image)))
            elif op == "recognize":
                result = normalize_text_rec_output(_run_text_rec_predict(text_recognizer, _ensure_rgb(image)))
            else:
                raise ValueError(f"Unsupported OCR worker op: {op}")
            write_response(protocol_stdout, {"ok": True, "result": result})
        except Exception as exc:
            write_response(protocol_stdout, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    main()
