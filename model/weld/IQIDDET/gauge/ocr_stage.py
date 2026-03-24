#!/usr/bin/env python3
"""OCR stage helpers for gauge pipeline."""

from __future__ import annotations

import base64
from collections import Counter
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

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
    ):
        self.device = str(device)
        self.det_model_name = det_model_name
        self.det_model_dir = det_model_dir
        self.rec_model_name = rec_model_name
        self.rec_model_dir = rec_model_dir
        self.python_bin = python_bin or sys.executable
        self.det_limit_side_len = int(det_limit_side_len) if det_limit_side_len is not None else None
        self.det_limit_type = str(det_limit_type) if det_limit_type else None
        self.repo_root = Path(__file__).resolve().parents[1]
        self.worker_script = Path(__file__).with_name("ocr_paddle_worker.py")
        self.process: Optional[subprocess.Popen[str]] = None
        self._start()

    def _start(self) -> None:
        cmd = [
            self.python_bin,
            str(self.worker_script),
            "--device",
            self.device,
        ]
        # 只有非 None 时才传参数；det/rec_model_dir 存在时 model_name 可为 None
        if self.det_model_name:
            cmd.extend(["--det-model-name", self.det_model_name])
        if self.rec_model_name:
            cmd.extend(["--rec-model-name", self.rec_model_name])
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
        ready = self._read_response()
        if not ready.get("ok"):
            raise RuntimeError(f"OCR worker failed to start: {ready.get('error', 'unknown error')}")

    def _read_response(self) -> Dict[str, Any]:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("OCR worker stdout is not available.")
        line = self.process.stdout.readline()
        if not line:
            returncode = self.process.poll() if self.process is not None else None
            raise RuntimeError(f"OCR worker exited unexpectedly with code {returncode}.")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse OCR worker response: {line.strip()}") from exc

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("OCR worker stdin is not available.")
        if self.process.poll() is not None:
            raise RuntimeError(f"OCR worker has already exited with code {self.process.returncode}.")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        response = self._read_response()
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


def _run_ocr_predict(ocr_engine, image: Any) -> Any:
    try:
        return ocr_engine.predict(input=image)
    except TypeError:
        pass

    try:
        return ocr_engine.predict(image)
    except Exception:
        pass

    return ocr_engine.ocr(image, cls=False)


def _run_text_det_predict(text_detector, image: Any) -> Any:
    if hasattr(text_detector, "detect"):
        return text_detector.detect(image)
    try:
        return text_detector.predict(input=image)
    except TypeError:
        return text_detector.predict(image)


def _run_text_rec_predict(text_recognizer, image: Any) -> Any:
    if hasattr(text_recognizer, "recognize"):
        return text_recognizer.recognize(image)
    try:
        return text_recognizer.predict(input=image)
    except TypeError:
        return text_recognizer.predict(image)


def _ensure_rgb(image: Any) -> Any:
    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        if image.ndim == 3 and image.shape[2] == 1:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        if image.ndim == 3 and image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image


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


def infer_roi_ocr(
    text_detector,
    text_recognizer,
    roi_image: Any,
    min_score: float = 0.0,
    text_orientation_corrector=None,
    text_orientation_verbose: bool = False,
) -> Dict[str, Any]:
    """Run OCR on an image via text detection, per-crop correction and text recognition."""
    from gauge.pipeline_utils import crop_rotated_polygon

    pipeline_start = time.perf_counter()
    det_ms = 0.0
    orientation_ms = 0.0
    rec_ms = 0.0

    def _build_timing_payload() -> Dict[str, float]:
        total_ms = (time.perf_counter() - pipeline_start) * 1000.0
        return {
            "text_det_ms": round(float(det_ms), 3),
            "text_orientation_ms": round(float(orientation_ms), 3),
            "text_rec_ms": round(float(rec_ms), 3),
            "text_total_ms": round(float(total_ms), 3),
        }

    try:
        det_input = _ensure_rgb(roi_image)
        det_start = time.perf_counter()
        det_raw_output = _run_text_det_predict(text_detector, det_input)
        det_ms = (time.perf_counter() - det_start) * 1000.0
        det_output = normalize_text_det_output(det_raw_output)
        dt_polys = det_output.get("dt_polys", [])
        dt_scores = det_output.get("dt_scores", [])
        if not dt_polys:
            return {
                "status": "no_text",
                "texts": [],
                "scores": [],
                "items": [],
                "all_items": [],
                "num_items": 0,
                "selected_variant": "none",
                "all_texts_original": [],
                "all_texts_mirror": [],
                "det_box_count": 0,
                "rec_item_count": 0,
                "timings_ms": _build_timing_payload(),
            }

        all_items: List[Dict[str, Any]] = []
        item_errors: List[Dict[str, Any]] = []
        success_count = 0

        for idx, poly in enumerate(dt_polys):
            try:
                poly_np = np.array(poly, dtype=np.float32).reshape(-1, 2)
                crop, _ = crop_rotated_polygon(roi_image, poly_np)
                if crop is None:
                    continue

                orientation_info = {
                    "label": None,
                    "confidence": None,
                    "status": "disabled" if text_orientation_corrector is None else "unknown",
                    "corrected": False,
                    "actions": None,
                }
                rec_image = crop.copy()
                if text_orientation_corrector is not None:
                    orientation_start = time.perf_counter()
                    rec_image, orientation_info = text_orientation_corrector.correct_image(
                        crop,
                        verbose=text_orientation_verbose,
                    )
                    orientation_ms += (time.perf_counter() - orientation_start) * 1000.0

                rec_input = _ensure_rgb(rec_image)
                rec_start = time.perf_counter()
                rec_raw_output = _run_text_rec_predict(text_recognizer, rec_input)
                rec_ms += (time.perf_counter() - rec_start) * 1000.0
                rec_output = normalize_text_rec_output(rec_raw_output)
                text = rec_output.get("rec_text", "")
                score = rec_output.get("rec_score")
                accepted_by_score = score is None or score >= min_score
                item_status = "ok"
                if not text:
                    item_status = "empty"
                elif not accepted_by_score:
                    item_status = "low_score"
                success_count += 1
                all_items.append(
                    {
                        "crop_index": idx,
                        "text": text,
                        "score": score,
                        "box": poly_np.tolist(),
                        "det_score": float(dt_scores[idx]) if idx < len(dt_scores) and dt_scores[idx] is not None else None,
                        "crop_size": [int(crop.shape[1]), int(crop.shape[0])],
                        "status": item_status,
                        "accepted_by_score": bool(accepted_by_score),
                        "orientation": orientation_info,
                    }
                )
            except Exception as exc:
                item_errors.append({"crop_index": idx, "error": str(exc)})
                all_items.append(
                    {
                        "crop_index": idx,
                        "text": "",
                        "score": None,
                        "box": np.array(poly, dtype=np.float32).reshape(-1, 2).tolist(),
                        "det_score": float(dt_scores[idx]) if idx < len(dt_scores) and dt_scores[idx] is not None else None,
                        "status": "error",
                        "accepted_by_score": False,
                        "error": str(exc),
                        "orientation": {
                            "label": None,
                            "confidence": None,
                            "status": "error",
                            "corrected": False,
                            "actions": None,
                        },
                    }
                )

        scored_items = [item for item in all_items if item.get("accepted_by_score")]
        jb_items = _filter_items_with_jb(scored_items)
        texts = [str(item.get("text", "")) for item in scored_items]
        scores = [item.get("score") for item in scored_items]
        all_texts = [str(item.get("text", "")) for item in all_items if item.get("text")]

        if scored_items:
            status = "ok"
        elif success_count == 0 and item_errors:
            status = "error"
        else:
            status = "no_text_after_score"

        return {
            "status": status,
            "texts": texts,
            "scores": scores,
            "items": scored_items,
            "all_items": all_items,
            "num_items": len(scored_items),
            "selected_variant": "det_rec",
            "all_texts_original": all_texts,
            "all_texts_mirror": [],
            "det_box_count": len(dt_polys),
            "rec_item_count": len(all_items),
            "jb_items": jb_items,
            "jb_texts": [str(item.get("text", "")) for item in jb_items],
            "jb_item_count": len(jb_items),
            "item_errors": item_errors,
            "timings_ms": _build_timing_payload(),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "texts": [],
            "scores": [],
            "items": [],
            "all_items": [],
            "num_items": 0,
            "selected_variant": "error",
            "all_texts_original": [],
            "all_texts_mirror": [],
            "det_box_count": 0,
            "rec_item_count": 0,
            "item_errors": [{"crop_index": None, "error": str(exc)}],
            "timings_ms": _build_timing_payload(),
        }


def build_ocr_statistics(results: List[Dict[str, Any]], topk: int = 200) -> Dict[str, Any]:
    """Aggregate OCR-level stats across all image records."""
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


def draw_ocr_on_roi(roi_image: np.ndarray, ocr_result: Dict[str, Any]) -> np.ndarray:
    """Draw OCR polygons and texts on ROI image."""
    vis = roi_image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    items = ocr_result.get("all_items") or ocr_result.get("items", []) or []
    for item in items:
        box = item.get("box")
        text = str(item.get("text", ""))
        score = item.get("score")
        if box is None:
            continue
        try:
            pts = np.array(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            continue
        if pts.shape[0] < 3:
            continue
        pts_i = pts.astype(np.int32).reshape(-1, 1, 2)
        color = (0, 255, 0) if item.get("status") != "error" else (0, 0, 255)
        cv2.polylines(vis, [pts_i], isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA)

        label = text or f"[{item.get('status', 'empty')}]"
        if score is not None:
            label = f"{label} ({float(score):.2f})"
        x = int(np.min(pts[:, 0]))
        y = int(np.min(pts[:, 1])) - 6
        y = max(y, 18)
        cv2.putText(
            vis,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    return vis


def draw_recognition_result(crop_image: np.ndarray, item: Dict[str, Any]) -> np.ndarray:
    """Draw recognized text and optional orientation action under a crop image."""
    vis = crop_image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    text = str(item.get("text", "")) or f"[{item.get('status', 'empty')}]"
    score = item.get("score")
    orientation = item.get("orientation") or {}
    actions = orientation.get("actions") if orientation.get("corrected") else None

    lines = [text if score is None else f"{text} ({float(score):.2f})"]
    if actions:
        lines.append(str(actions))

    line_height = 24
    footer_height = line_height * len(lines) + 12
    canvas = np.full((vis.shape[0] + footer_height, vis.shape[1], 3), 255, dtype=np.uint8)
    canvas[: vis.shape[0], : vis.shape[1]] = vis

    y = vis.shape[0] + 22
    for line in lines:
        cv2.putText(
            canvas,
            line,
            (8, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            lineType=cv2.LINE_AA,
        )
        y += line_height
    return canvas


def build_ocr_item_debug_images(roi_image: np.ndarray, ocr_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rebuild crop / corrected crop / rec vis images from OCR result metadata."""
    from gauge.pipeline_utils import crop_rotated_polygon

    debug_rows: List[Dict[str, Any]] = []
    items = ocr_result.get("all_items", []) or []
    for item in items:
        box = item.get("box")
        if box is None:
            continue
        try:
            pts = np.array(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            continue
        crop, _ = crop_rotated_polygon(roi_image, pts)
        if crop is None:
            continue

        rec_input = crop.copy()
        orientation = item.get("orientation") or {}
        label = orientation.get("label")
        if label is not None and orientation.get("status") != "disabled":
            from gauge.ocr_orientation import OCRTextOrientationCorrector

            rec_input, _ = OCRTextOrientationCorrector.restore_image(crop, int(label))

        debug_rows.append(
            {
                "crop_index": int(item.get("crop_index", len(debug_rows))),
                "crop_image": crop,
                "rec_input_image": rec_input,
                "rec_result_image": draw_recognition_result(rec_input, item),
                "text": item.get("text", ""),
                "score": item.get("score"),
            }
        )
    return debug_rows
