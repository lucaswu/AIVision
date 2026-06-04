#!/usr/bin/env python3
"""Subprocess runtime client for PaddleOCR worker protocol."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import selectors
import subprocess
import sys
import threading
from typing import Any, Dict, Optional

import cv2
import numpy as np


class PaddleOCRSubprocessClient:
    """Persistent PaddleOCR worker running in a separate process."""

    def __init__(
        self,
        device: str = "gpu",
        det_model_name: str = "PP-OCRv5_server_det",
        det_model_dir: Optional[str] = None,
        rec_model_name: str = "en_PP-OCRv5_mobile_rec",
        rec_model_dir: Optional[str] = None,
        python_bin: Optional[str] = None,
        det_limit_side_len: Optional[int] = None,
        det_limit_type: Optional[str] = None,
        startup_timeout_s: float = 120.0,
        request_timeout_s: float = 60.0,
    ):
        self.device = str(device)
        self.det_model_name = det_model_name
        self.det_model_dir = det_model_dir
        self.rec_model_name = rec_model_name
        self.rec_model_dir = rec_model_dir
        self.python_bin = python_bin or sys.executable
        self.det_limit_side_len = int(det_limit_side_len) if det_limit_side_len is not None else None
        self.det_limit_type = str(det_limit_type) if det_limit_type else None
        self.startup_timeout_s = float(startup_timeout_s)
        self.request_timeout_s = float(request_timeout_s)
        self.repo_root = Path(__file__).resolve().parents[3]
        self.worker_script = Path(__file__).resolve().parent / "ocr_paddle_worker.py"
        self.process: Optional[subprocess.Popen[str]] = None
        self._lock = threading.Lock()
        self._start()

    def _start(self) -> None:
        cmd = [
            self.python_bin,
            str(self.worker_script),
            "--device",
            self.device,
            "--det-model-name",
            self.det_model_name,
            "--rec-model-name",
            self.rec_model_name,
        ]
        if self.det_model_dir:
            cmd.extend(["--det-model-dir", str(self.det_model_dir)])
        if self.rec_model_dir:
            cmd.extend(["--rec-model-dir", str(self.rec_model_dir)])
        if self.det_limit_side_len is not None:
            cmd.extend(["--det-limit-side-len", str(self.det_limit_side_len)])
        if self.det_limit_type:
            cmd.extend(["--det-limit-type", str(self.det_limit_type)])

        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
        )
        ready = self._read_response(timeout_s=self.startup_timeout_s)
        if not ready.get("ok"):
            raise RuntimeError(f"OCR worker failed to start: {ready.get('error', 'unknown error')}")

    def _readline_with_timeout(self, timeout_s: float) -> str:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("OCR worker stdout is not available.")
        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            events = selector.select(timeout=float(timeout_s))
            if not events:
                raise TimeoutError("OCR worker response timed out")
            return self.process.stdout.readline()
        finally:
            selector.close()

    def _read_response(self, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        timeout = self.request_timeout_s if timeout_s is None else float(timeout_s)
        try:
            line = self._readline_with_timeout(timeout)
        except TimeoutError as exc:
            self.close()
            raise RuntimeError(str(exc)) from exc
        if not line:
            returncode = self.process.poll() if self.process is not None else None
            raise RuntimeError(f"OCR worker exited unexpectedly with code {returncode}.")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse OCR worker response: {line.strip()}") from exc

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if self.process is None or self.process.stdin is None:
                raise RuntimeError("OCR worker stdin is not available.")
            if self.process.poll() is not None:
                raise RuntimeError(f"OCR worker has already exited with code {self.process.returncode}.")
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            response = self._read_response(timeout_s=self.request_timeout_s)
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "OCR worker request failed."))
            return response

    @staticmethod
    def _encode_image(image: np.ndarray) -> Dict[str, Any]:
        ok, buffer = cv2.imencode(".png", image)
        if not ok:
            raise ValueError("Failed to encode image for OCR worker.")
        return {
            "format": "png_base64",
            "data": base64.b64encode(buffer.tobytes()).decode("ascii"),
        }

    def detect(self, image: np.ndarray) -> Dict[str, Any]:
        response = self._request({"op": "detect", "image": self._encode_image(image)})
        return response.get("result", {})

    def recognize(self, image: np.ndarray) -> Dict[str, Any]:
        response = self._request({"op": "recognize", "image": self._encode_image(image)})
        return response.get("result", {})

    def close(self) -> None:
        if self.process is None:
            return
        proc = self.process
        self.process = None
        try:
            if proc.poll() is None and proc.stdin is not None:
                proc.stdin.write(json.dumps({"op": "close"}) + "\n")
                proc.stdin.flush()
        except Exception:
            pass
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
