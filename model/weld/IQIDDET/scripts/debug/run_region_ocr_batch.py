#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Batch region OCR entry for cropped text images."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gauge.pipeline_utils import SUPPORTED_IMAGE_EXTS, collect_images, ensure_dir
from gauge.region_ocr_service import RegionOCRService

try:  # pragma: no cover
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(items, **_kwargs):
        return items


DEFAULT_IMAGE_DIR = "/home/cht/code/IQIdet/local/OCRdatasets/debug0411"
DEFAULT_OUTPUT_JSON = "outputs/region_ocr_debug0411/region_ocr_results.json"
DEFAULT_REC_MODEL_CANDIDATES = (
    "models/OCR_rec_inference_best_accuracy0325",
)
VIS_MIN_WIDTH = 960
VIS_SIDE_PAD = 24
VIS_TOP_PAD = 20
VIS_BOTTOM_PAD = 20
VIS_LINE_HEIGHT = 26
VIS_IMAGE_GAP = 12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch region OCR for cropped text images with optional orientation correction."
    )
    parser.add_argument("--image-path", help="Single image path to process.")
    parser.add_argument("--image-dir", default=DEFAULT_IMAGE_DIR, help="Batch image directory to process.")
    parser.add_argument("--image-list", help="Optional text file with image paths or directories (one per line).")
    parser.add_argument("--max-images", type=int, help="Max images to process.")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON, help="Output JSON file path.")
    parser.add_argument(
        "--vis-dir",
        help="Directory used to save visualization images. Defaults to <output-json-parent>/vis.",
    )
    parser.add_argument("--no-vis", action="store_true", help="Disable saving OCR visualization images.")

    parser.add_argument(
        "--ocr-rec-model-dir",
        help="Optional local PaddleOCR recognition model directory. If omitted, local defaults are auto-resolved.",
    )
    parser.add_argument(
        "--ocr-rec-model-name",
        default="en_PP-OCRv5_mobile_rec",
        help="PaddleOCR text recognition model name.",
    )
    parser.add_argument(
        "--ocr-device",
        choices=["cpu", "gpu"],
        default="gpu",
        help="PaddleOCR device used by the recognition subprocess.",
    )
    parser.add_argument(
        "--enhance-mode",
        choices=["windowing", "gray", "original"],
        default="windowing",
        help="Preprocess mode before orientation correction and OCR recognition.",
    )
    parser.add_argument(
        "--disable-orientation",
        action="store_true",
        help="Disable text-crop orientation correction before OCR recognition.",
    )
    parser.add_argument(
        "--ocr-orientation-model",
        default="models/ocr_orientation_model.pth",
        help="Text-crop orientation correction model weights (.pth).",
    )
    parser.add_argument("--ocr-orientation-device", help="Orientation correction device, e.g. cuda:0/cpu.")
    parser.add_argument("--ocr-orientation-verbose", action="store_true", help="Print per-image orientation diagnostics.")
    parser.add_argument(
        "--python-bin",
        help="Optional Python interpreter used by the PaddleOCR subprocess worker. Defaults to the current interpreter.",
    )
    return parser.parse_args()


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    return value


def _resolve_cli_path(value: str, base: Optional[Path] = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    base_dir = (base or Path.cwd()).resolve()
    return (base_dir / path).resolve()


def _resolve_default_rec_model_dir(repo_root: Path) -> Path:
    for candidate in DEFAULT_REC_MODEL_CANDIDATES:
        candidate_path = _resolve_cli_path(candidate, repo_root)
        if candidate_path.is_dir():
            return candidate_path
    joined = ", ".join(DEFAULT_REC_MODEL_CANDIDATES)
    raise FileNotFoundError(f"No local OCR recognition model directory found. Tried: {joined}")


def _resolve_rec_model_dir(raw_value: Optional[str], repo_root: Path) -> Path:
    if raw_value:
        rec_model_dir = _resolve_cli_path(raw_value)
        if not rec_model_dir.is_dir():
            raise FileNotFoundError(f"OCR recognition model directory not found: {rec_model_dir}")
        return rec_model_dir
    return _resolve_default_rec_model_dir(repo_root)


def collect_input_images(
    image_path: Optional[str] = None,
    image_dir: Optional[str] = None,
    image_list: Optional[str] = None,
    max_images: Optional[int] = None,
) -> list[Path]:
    if image_path:
        paths = [Path(image_path).resolve()]
    else:
        paths = collect_images(
            Path(image_dir).resolve() if image_dir else None,
            Path(image_list).resolve() if image_list else None,
            max_images=max_images,
        )
    if max_images is not None:
        paths = paths[:max_images]
    return paths


def _get_rel_path(image_path: Path, image_root: Optional[Path]) -> Path:
    if image_root is None:
        return Path(image_path.name)
    try:
        return image_path.relative_to(image_root)
    except ValueError:
        return Path(image_path.name)


def _build_timing_stats(results: list[Dict[str, Any]]) -> Dict[str, Any]:
    values_by_key: Dict[str, list[float]] = {}
    for record in results:
        timings = record.get("timings_ms") or {}
        if record.get("status") == "error" or not timings:
            continue
        for key, value in timings.items():
            try:
                values_by_key.setdefault(str(key), []).append(float(value))
            except (TypeError, ValueError):
                continue

    stats: Dict[str, Any] = {}
    for key, values in sorted(values_by_key.items()):
        if not values:
            continue
        stats[key] = {
            "count": len(values),
            "mean_ms": round(sum(values) / len(values), 3),
            "min_ms": round(min(values), 3),
            "max_ms": round(max(values), 3),
        }
    return stats


def _build_summary(results: list[Dict[str, Any]]) -> Dict[str, Any]:
    ok_total = sum(1 for item in results if item.get("status") == "ok")
    empty_total = sum(1 for item in results if item.get("status") == "empty")
    error_total = sum(1 for item in results if item.get("status") == "error")
    recognized_total = sum(1 for item in results if item.get("text"))
    orientation_corrected_total = sum(
        1 for item in results if bool((item.get("orientation") or {}).get("corrected"))
    )
    vis_total = sum(1 for item in results if item.get("vis_path"))
    return {
        "images_total": len(results),
        "ok_total": ok_total,
        "empty_total": empty_total,
        "error_total": error_total,
        "recognized_total": recognized_total,
        "orientation_corrected_total": orientation_corrected_total,
        "visualized_total": vis_total,
        "timings_ms": _build_timing_stats(results),
    }


def _normalize_vis_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " | ").replace("\t", " ")
    return " ".join(text.split())


def _wrap_text(text: str, max_width: int, font_scale: float, thickness: int) -> list[str]:
    clean = _normalize_vis_text(text)
    if not clean:
        return [""]

    words = clean.split(" ")
    lines: list[str] = []
    current = ""
    font_face = cv2.FONT_HERSHEY_SIMPLEX

    def fits(candidate: str) -> bool:
        width = cv2.getTextSize(candidate, font_face, font_scale, thickness)[0][0]
        return width <= max_width

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if fits(candidate):
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if fits(word):
            current = word
            continue

        chunk = ""
        for ch in word:
            next_chunk = f"{chunk}{ch}"
            if chunk and not fits(next_chunk):
                lines.append(chunk)
                chunk = ch
            else:
                chunk = next_chunk
        current = chunk

    if current:
        lines.append(current)
    return lines or [clean]


def _status_color(status: str) -> tuple[int, int, int]:
    normalized = str(status or "").lower()
    if normalized == "ok":
        return (48, 160, 80)
    if normalized == "empty":
        return (0, 140, 255)
    return (40, 40, 220)


def _to_bgr_image(image: Optional[np.ndarray]) -> np.ndarray:
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        return np.full((160, 480, 3), 245, dtype=np.uint8)
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 1:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image.copy()


def _build_visualization(image: Optional[np.ndarray], image_path: Path, record: Dict[str, Any]) -> np.ndarray:
    vis_image = _to_bgr_image(image)
    img_h, img_w = vis_image.shape[:2]
    canvas_w = max(int(img_w), VIS_MIN_WIDTH)
    text_width = canvas_w - VIS_SIDE_PAD * 2
    status = str(record.get("status") or "unknown")
    orientation = record.get("orientation") or {}
    score = record.get("score")
    timings = record.get("timings_ms") or {}
    total_ms = timings.get("total_ms")
    error_text = _normalize_vis_text(record.get("error"))

    header_lines = [
        f"file: {image_path.name}",
        f"status: {status}    score: {('%.4f' % float(score)) if score is not None else 'n/a'}    total_ms: {('%.3f' % float(total_ms)) if total_ms is not None else 'n/a'}",
        f"text: {_normalize_vis_text(record.get('text')) or '<empty>'}",
        f"normalized: {_normalize_vis_text(record.get('normalized_text')) or '<empty>'}",
        "orientation: "
        f"{_normalize_vis_text(orientation.get('status')) or 'n/a'}"
        f"    corrected: {bool(orientation.get('corrected'))}"
        f"    confidence: {('%.4f' % float(orientation.get('confidence'))) if orientation.get('confidence') is not None else 'n/a'}",
    ]
    if error_text:
        header_lines.append(f"error: {error_text}")

    wrapped_lines: list[str] = []
    for line in header_lines:
        wrapped_lines.extend(_wrap_text(line, text_width, font_scale=0.62, thickness=1))

    header_h = VIS_TOP_PAD + VIS_BOTTOM_PAD + VIS_LINE_HEIGHT * len(wrapped_lines)
    canvas_h = header_h + VIS_IMAGE_GAP + img_h
    canvas = np.full((canvas_h, canvas_w, 3), 250, dtype=np.uint8)
    accent = _status_color(status)

    cv2.rectangle(canvas, (0, 0), (canvas_w - 1, header_h - 1), (245, 245, 245), thickness=-1)
    cv2.rectangle(canvas, (0, 0), (11, canvas_h - 1), accent, thickness=-1)
    cv2.rectangle(canvas, (0, 0), (canvas_w - 1, canvas_h - 1), (220, 220, 220), thickness=1)

    y = VIS_TOP_PAD + 2
    for idx, line in enumerate(wrapped_lines):
        color = accent if idx == 0 else (45, 45, 45)
        cv2.putText(
            canvas,
            line,
            (VIS_SIDE_PAD, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            color,
            1,
            cv2.LINE_AA,
        )
        y += VIS_LINE_HEIGHT

    image_x = max(0, (canvas_w - img_w) // 2)
    image_y = header_h + VIS_IMAGE_GAP
    canvas[image_y : image_y + img_h, image_x : image_x + img_w] = vis_image
    cv2.rectangle(
        canvas,
        (image_x, image_y),
        (image_x + img_w - 1, image_y + img_h - 1),
        accent,
        thickness=2,
    )
    return canvas


def _save_visualization(
    vis_dir: Path,
    image: Optional[np.ndarray],
    image_path: Path,
    image_root: Optional[Path],
    record: Dict[str, Any],
) -> str:
    rel_path = _get_rel_path(image_path, image_root).with_suffix(".png")
    output_path = vis_dir / rel_path
    ensure_dir(output_path.parent)
    vis_image = _build_visualization(image=image, image_path=image_path, record=record)
    ok = cv2.imwrite(str(output_path), vis_image)
    if not ok:
        raise RuntimeError(f"Failed to write visualization image: {output_path}")
    return str(output_path)


def main() -> None:
    args = parse_args()
    repo_root = REPO_ROOT

    output_json = _resolve_cli_path(args.output_json)
    ensure_dir(output_json.parent)
    vis_dir = None
    if not args.no_vis:
        vis_dir = _resolve_cli_path(args.vis_dir) if args.vis_dir else output_json.parent / "vis"
        ensure_dir(vis_dir)

    image_paths = collect_input_images(
        image_path=args.image_path,
        image_dir=args.image_dir,
        image_list=args.image_list,
        max_images=args.max_images,
    )
    image_root = _resolve_cli_path(args.image_dir) if args.image_dir and not args.image_path else None
    ocr_rec_model_dir = _resolve_rec_model_dir(args.ocr_rec_model_dir, repo_root)

    orientation_model = None
    if not args.disable_orientation:
        orientation_model = _resolve_cli_path(args.ocr_orientation_model)
        if not orientation_model.is_file():
            raise FileNotFoundError(f"OCR orientation model file not found: {orientation_model}")

    service = RegionOCRService(
        ocr_rec_model_dir=str(ocr_rec_model_dir),
        ocr_rec_model_name=args.ocr_rec_model_name,
        ocr_device=args.ocr_device,
        enhance_mode=args.enhance_mode,
        enable_orientation=not args.disable_orientation,
        ocr_orientation_model=str(orientation_model) if orientation_model is not None else args.ocr_orientation_model,
        ocr_orientation_device=args.ocr_orientation_device,
        ocr_orientation_verbose=args.ocr_orientation_verbose,
        python_bin=args.python_bin,
    )

    results = []
    try:
        for image_path in tqdm(image_paths, desc="Region OCR"):
            width = None
            height = None
            image = None
            try:
                image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
                if image is None:
                    raise FileNotFoundError(f"Failed to read image: {image_path}")
                height, width = int(image.shape[0]), int(image.shape[1])
                record = service.recognize_image(image)
                record.update(
                    {
                        "image_path": str(image_path),
                        "relative_path": str(_get_rel_path(image_path, image_root)),
                    }
                )
            except Exception as exc:
                record = {
                    "status": "error",
                    "text": "",
                    "normalized_text": "",
                    "score": None,
                    "width": width,
                    "height": height,
                    "preprocess_mode": args.enhance_mode,
                    "orientation": {},
                    "timings_ms": {},
                    "image_path": str(image_path),
                    "relative_path": str(_get_rel_path(image_path, image_root)),
                    "error": str(exc),
                }
            if vis_dir is not None:
                try:
                    record["vis_path"] = _save_visualization(
                        vis_dir=vis_dir,
                        image=image,
                        image_path=image_path,
                        image_root=image_root,
                        record=record,
                    )
                except Exception as exc:
                    record["vis_error"] = str(exc)
            results.append(record)
    finally:
        service.close()

    summary = _build_summary(results)
    payload = {
        "schema": "region_ocr_batch_v1",
        "ok": True,
        "fatal_error": None,
        "meta": {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "image_root": str(image_root) if image_root is not None else None,
            "supported_exts": list(SUPPORTED_IMAGE_EXTS),
            "script_python": sys.executable,
            "ocr_worker_python": args.python_bin or sys.executable,
            "ocr_device": args.ocr_device,
            "ocr_rec_model_name": args.ocr_rec_model_name,
            "ocr_rec_model_dir": str(ocr_rec_model_dir),
            "enhance_mode": args.enhance_mode,
            "enable_orientation": not args.disable_orientation,
            "ocr_orientation_model": str(orientation_model) if orientation_model is not None else None,
            "ocr_orientation_device": args.ocr_orientation_device,
            "ocr_orientation_verbose": args.ocr_orientation_verbose,
            "default_image_dir": DEFAULT_IMAGE_DIR,
            "vis_dir": str(vis_dir) if vis_dir is not None else None,
        },
        "summary": summary,
        "results": results,
    }

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(payload), f, indent=2, ensure_ascii=False)

    print(f"Region OCR finished, processed {summary['images_total']} images.")
    print(
        "Status counts: "
        f"ok={summary['ok_total']}, "
        f"empty={summary['empty_total']}, "
        f"error={summary['error_total']}"
    )
    if vis_dir is not None:
        print(f"Visualization dir: {vis_dir}")
    print(f"Output JSON: {output_json}")


if __name__ == "__main__":
    main()
