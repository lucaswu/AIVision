#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""IQI debug pipeline with ROI, OCR, wire inference and visualization."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

from gauge.iqi_inferencer import (
    IQIInferencer,
    build_iqi_statistics,
    collect_input_images,
    save_debug_visualizations,
)
from gauge.iqi_rules import DEFAULT_ALLOWED_NUMBERS_SPEC
from gauge.pipeline_utils import SUPPORTED_IMAGE_EXTS, ensure_dir

try:  # pragma: no cover
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(items, **_kwargs):
        return items


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IQI debug inference pipeline.")
    parser.add_argument("--image-path", help="Single image path to process.")
    parser.add_argument("--image-dir", help="Batch image directory to process.")
    parser.add_argument("--image-list", help="Optional text file with image paths (one per line).")
    parser.add_argument("--output-dir", default="outputs/iqi_debug", help="Output root directory.")
    parser.add_argument("--results-json", default="iqi_results.json", help="Per-image JSON filename.")
    parser.add_argument("--stats-json", "--ocr-stats-json", dest="stats_json", default="iqi_stats.json", help="Summary JSON filename.")
    parser.add_argument("--max-images", type=int, help="Max images to process.")
    parser.add_argument("--vis", action="store_true", help="Save visualizations to output_dir/vis.")
    parser.add_argument("--debug-timer", action="store_true", help="Collect per-step timing statistics and save a timer JSON.")
    parser.add_argument("--timer-json", default="iqi_timer_stats.json", help="Timing summary JSON filename used with --debug-timer.")

    parser.add_argument("--gauge-weights", required=True, help="OBB gauge detector weights.")
    parser.add_argument("--gauge-conf", type=float, default=0.25, help="OBB confidence threshold.")
    parser.add_argument("--gauge-iou", type=float, default=0.45, help="OBB IoU threshold.")
    parser.add_argument("--gauge-imgsz", type=int, default=640, help="OBB inference image size.")
    parser.add_argument("--gauge-device", default=None, help="OBB device, e.g. 0/cuda:0/cpu.")
    parser.add_argument(
        "--gauge-select",
        choices=["conf", "area"],
        default="conf",
        help="How to pick the ROI when multiple detections exist.",
    )
    parser.add_argument("--gauge-class", type=int, help="Optional class id filter.")

    parser.add_argument("--fclip-ckpt", help="FClip checkpoint used for wire count inference.")
    parser.add_argument("--fclip-device", default=None, help="FClip device, e.g. cuda:0/cpu.")
    parser.add_argument("--fclip-config", default="models/fclip_config.yaml", help="FClip model yaml.")
    parser.add_argument("--fclip-params", default="params.yaml", help="FClip params yaml.")
    parser.add_argument("--fclip-threshold", type=float, help="Optional FClip line parsing threshold override.")

    parser.add_argument(
        "--enhance-mode",
        choices=["original", "windowing"],
        default="windowing",
        help="Image enhancement mode before OCR/FClip.",
    )
    parser.add_argument("--no-rotate", action="store_true", help="Disable width>height -> CCW90 rotation.")

    parser.add_argument("--enable-correction", action="store_true", help="Enable weld orientation correction before ROI detection.")
    parser.add_argument("--correction-model", help="Orientation correction model weights (.pth). Required when --enable-correction is set.")
    parser.add_argument("--correction-device", help="Orientation correction device, e.g. cuda:0/cpu.")
    parser.add_argument("--correction-verbose", action="store_true", help="Print per-image orientation correction diagnostics.")

    parser.add_argument(
        "--ocr-device",
        choices=["cpu", "gpu"],
        default="gpu",
        help="PaddleOCR device used by TextDetection/TextRecognition.",
    )
    parser.add_argument(
        "--ocr-det-model-name",
        default="PP-OCRv5_server_det",
        help="PaddleOCR text detection model name.",
    )
    parser.add_argument("--ocr-det-model-dir", help="Optional local PaddleOCR text detection model directory.")
    parser.add_argument(
        "--ocr-rec-model-name",
        default="en_PP-OCRv5_mobile_rec",
        help="PaddleOCR text recognition model name.",
    )
    parser.add_argument("--ocr-rec-model-dir", help="Optional local PaddleOCR text recognition model directory.")
    parser.add_argument("--ocr-min-score", type=float, default=0.0, help="Min OCR confidence score.")
    parser.add_argument("--ocr-det-limit-side-len", type=int, default=960, help="Resize OCR detection input so its longest side is no greater than this value.")
    parser.add_argument("--ocr-det-limit-type", default="max", choices=["max", "min"], help="PaddleOCR detection side-length limit type.")
    parser.add_argument("--ocr-topk", type=int, default=200, help="Top-K terms kept in OCR statistics.")
    parser.add_argument(
        "--ocr-number-range",
        default=DEFAULT_ALLOWED_NUMBERS_SPEC,
        help="Allowed IQI OCR marker numbers, e.g. 6,10-15.",
    )

    parser.add_argument(
        "--enable-ocr-orientation",
        action="store_true",
        help="Enable text-crop orientation correction before OCR recognition.",
    )
    parser.add_argument(
        "--ocr-orientation-model",
        default="models/ocr_orientation_model.pth",
        help="Text-crop orientation correction model weights (.pth).",
    )
    parser.add_argument("--ocr-orientation-device", help="Text-crop orientation correction device, e.g. cuda:0/cpu.")
    parser.add_argument("--ocr-orientation-verbose", action="store_true", help="Print per-crop OCR orientation diagnostics.")
    return parser.parse_args()


def _to_jsonable(value: Any) -> Any:
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


def _get_rel_path(image_path: Path, image_root: Optional[Path]) -> Path:
    if image_root is None:
        return Path(image_path.name)
    try:
        return image_path.relative_to(image_root)
    except ValueError:
        return Path(image_path.name)


def _build_sample_dir(vis_dir: Path, image_path: Path, image_root: Optional[Path], result_name: str) -> Path:
    rel_path = _get_rel_path(image_path, image_root)
    safe_name = str(result_name or "unknown")
    return vis_dir / safe_name / rel_path.with_suffix("")


def _round_ms(value: float) -> float:
    return round(float(value), 3)


def _build_timer_summary(results: list[dict[str, Any]]) -> Dict[str, Any]:
    per_image = []
    step_values: Dict[str, list[float]] = {}

    for record in results:
        timings = record.get("timings_ms") or {}
        if not timings:
            continue
        normalized = {str(k): float(v) for k, v in timings.items()}
        per_image.append(
            {
                "image_path": record.get("image_path"),
                "result_code": int(record.get("result_code", 9001)),
                "result_name": record.get("result_name"),
                "timings_ms": {k: _round_ms(v) for k, v in normalized.items()},
            }
        )
        for key, value in normalized.items():
            step_values.setdefault(str(key), []).append(float(value))

    step_stats = {}
    for key, values in sorted(step_values.items()):
        arr = np.asarray(values, dtype=np.float64)
        step_stats[key] = {
            "count": int(arr.size),
            "mean_ms": _round_ms(arr.mean()),
            "p50_ms": _round_ms(np.percentile(arr, 50)),
            "p90_ms": _round_ms(np.percentile(arr, 90)),
            "min_ms": _round_ms(arr.min()),
            "max_ms": _round_ms(arr.max()),
            "total_ms": _round_ms(arr.sum()),
        }

    return {
        "images_with_timing": len(per_image),
        "step_stats_ms": step_stats,
        "per_image": per_image,
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)
    vis_dir = output_dir / "vis"
    if args.vis:
        ensure_dir(vis_dir)

    image_paths = collect_input_images(
        image_path=args.image_path,
        image_dir=args.image_dir,
        image_list=args.image_list,
        max_images=args.max_images,
    )
    image_root = Path(args.image_dir).resolve() if args.image_dir else None

    inferencer = IQIInferencer(
        gauge_weights=args.gauge_weights,
        fclip_ckpt=args.fclip_ckpt,
        gauge_conf=args.gauge_conf,
        gauge_iou=args.gauge_iou,
        gauge_imgsz=args.gauge_imgsz,
        gauge_device=args.gauge_device,
        gauge_select=args.gauge_select,
        gauge_class=args.gauge_class,
        enhance_mode=args.enhance_mode,
        rotate_roi=not args.no_rotate,
        enable_correction=args.enable_correction,
        correction_model=args.correction_model,
        correction_device=args.correction_device,
        correction_verbose=args.correction_verbose,
        ocr_device=args.ocr_device,
        ocr_det_model_name=args.ocr_det_model_name,
        ocr_det_model_dir=args.ocr_det_model_dir,
        ocr_rec_model_name=args.ocr_rec_model_name,
        ocr_rec_model_dir=args.ocr_rec_model_dir,
        ocr_det_limit_side_len=args.ocr_det_limit_side_len,
        ocr_det_limit_type=args.ocr_det_limit_type,
        ocr_min_score=args.ocr_min_score,
        ocr_number_range=args.ocr_number_range,
        enable_ocr_orientation=args.enable_ocr_orientation,
        ocr_orientation_model=args.ocr_orientation_model,
        ocr_orientation_device=args.ocr_orientation_device,
        ocr_orientation_verbose=args.ocr_orientation_verbose,
        fclip_device=args.fclip_device,
        fclip_model_config=args.fclip_config,
        fclip_params=args.fclip_params,
        fclip_threshold=args.fclip_threshold,
    )

    results = []
    try:
        for image_path in tqdm(image_paths, desc="IQI Debug"):
            record, artifacts = inferencer.infer_image_path(
                image_path,
                return_debug_artifacts=args.vis,
                debug_timer=args.debug_timer,
            )
            if args.vis and artifacts is not None and artifacts.get("image") is not None:
                vis_start = time.perf_counter()
                sample_dir = _build_sample_dir(vis_dir, image_path, image_root, str(record.get("result_name", "unknown")))
                record.update(
                    save_debug_visualizations(
                        output_dir=output_dir,
                        sample_dir=sample_dir,
                        image=artifacts["image"],
                        full_ocr_result=record.get("full_image_ocr") or record.get("ocr") or {},
                        full_ocr_image=artifacts.get("full_ocr_input"),
                        roi_info=record.get("roi") or {},
                        roi_image=artifacts.get("roi_image"),
                        roi_gray=artifacts.get("roi_gray"),
                        roi_ocr_result=record.get("roi_ocr") or {},
                        wire_result=record.get("wire") or {},
                    )
                )
                record["status_vis_dir"] = str(sample_dir.relative_to(output_dir))
                if args.debug_timer:
                    timings = dict(record.get("timings_ms") or {})
                    timings["visualization_ms"] = _round_ms((time.perf_counter() - vis_start) * 1000.0)
                    record["timings_ms"] = timings
            elif args.debug_timer:
                timings = dict(record.get("timings_ms") or {})
                timings.setdefault("visualization_ms", 0.0)
                record["timings_ms"] = timings
            results.append(record)
    finally:
        inferencer.close()

    stats = build_iqi_statistics(results, topk=args.ocr_topk)
    meta = {
        "schema": "iqi_debug_batch_v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "image_root": str(image_root) if image_root is not None else None,
        "supported_exts": list(SUPPORTED_IMAGE_EXTS),
        **inferencer.get_runtime_meta(),
        "enable_correction": args.enable_correction,
        "correction_model": args.correction_model,
        "correction_device": args.correction_device,
        "ocr_device": args.ocr_device,
        "ocr_det_model_name": args.ocr_det_model_name,
        "ocr_det_model_dir": args.ocr_det_model_dir,
        "ocr_rec_model_name": args.ocr_rec_model_name,
        "ocr_rec_model_dir": args.ocr_rec_model_dir,
        "ocr_number_range": args.ocr_number_range,
        "enable_ocr_orientation": args.enable_ocr_orientation,
        "ocr_orientation_model": args.ocr_orientation_model,
        "ocr_orientation_device": args.ocr_orientation_device,
        "debug_timer": bool(args.debug_timer),
    }

    payload = {
        "meta": meta,
        "summary": stats,
        "results": results,
    }

    timer_payload = None
    if args.debug_timer:
        timer_payload = {
            "meta": {
                "schema": "iqi_debug_timer_v1",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "image_root": str(image_root) if image_root is not None else None,
                "images_total": len(results),
                "max_images": args.max_images,
                "vis_enabled": bool(args.vis),
                "output_dir": str(output_dir),
                **inferencer.get_runtime_meta(),
            },
            "summary": _build_timer_summary(results),
        }

    results_path = Path(args.results_json)
    if not results_path.is_absolute():
        results_path = output_dir / results_path
    ensure_dir(results_path.parent)

    stats_path = Path(args.stats_json)
    if not stats_path.is_absolute():
        stats_path = output_dir / stats_path
    ensure_dir(stats_path.parent)

    timer_path = None
    if args.debug_timer:
        timer_path = Path(args.timer_json)
        if not timer_path.is_absolute():
            timer_path = output_dir / timer_path
        ensure_dir(timer_path.parent)

    with results_path.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(payload), f, indent=2, ensure_ascii=False)
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(stats), f, indent=2, ensure_ascii=False)
    if timer_path is not None and timer_payload is not None:
        with timer_path.open("w", encoding="utf-8") as f:
            json.dump(_to_jsonable(timer_payload), f, indent=2, ensure_ascii=False)

    print(f"\nIQI debug 推理完成，共处理 {len(results)} 张图像。")
    print(f"结果JSON: {results_path}")
    print(f"统计JSON: {stats_path}")
    if timer_path is not None:
        print(f"耗时JSON: {timer_path}")


if __name__ == "__main__":
    main()
