#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Batch IQI grade inference entry for delivery/integration."""

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
    build_delivery_record,
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
    parser = argparse.ArgumentParser(description="Batch IQI grade inference for delivery/integration.")
    parser.add_argument("--image-path", help="Single image path to process.")
    parser.add_argument("--image-dir", help="Batch image directory to process.")
    parser.add_argument("--image-list", help="Optional text file with image paths or directories (one per line).")
    parser.add_argument("--max-images", type=int, help="Max images to process.")
    parser.add_argument("--output-json", default="outputs/iqi_grade_infer/iqi_grade_results.json", help="Output JSON file path.")
    parser.add_argument("--vis-dir", help="Optional directory to save debug visualizations.")

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

    parser.add_argument("--fclip-ckpt", required=True, help="FClip checkpoint used for wire count inference.")
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

    parser.add_argument(
        "--ocr-device",
        choices=["cpu", "gpu"],
        default="gpu",
        help="PaddleOCR device used by TextDetection/TextRecognition.",
    )
    parser.add_argument("--ocr-det-model-name", default="PP-OCRv5_server_det", help="PaddleOCR text detection model name.")
    parser.add_argument("--ocr-det-model-dir", help="Optional local PaddleOCR text detection model directory.")
    parser.add_argument("--ocr-rec-model-name", default="en_PP-OCRv5_mobile_rec", help="PaddleOCR text recognition model name.")
    parser.add_argument("--ocr-rec-model-dir", help="Optional local PaddleOCR text recognition model directory.")
    parser.add_argument("--ocr-min-score", type=float, default=0.0, help="Min OCR confidence score.")
    parser.add_argument("--ocr-det-limit-side-len", type=int, default=960, help="Resize OCR detection input so its longest side is no greater than this value.")
    parser.add_argument("--ocr-det-limit-type", default="max", choices=["max", "min"], help="PaddleOCR detection side-length limit type.")
    parser.add_argument("--ocr-topk", type=int, default=200, help="Top-K terms kept in OCR statistics.")
    parser.add_argument(
        "--ocr-number-range",
        default=DEFAULT_ALLOWED_NUMBERS_SPEC,
        help="Allowed OCR marker numbers, e.g. 6,10-15.",
    )

    parser.add_argument("--enable-ocr-orientation", action="store_true", help="Enable text-crop orientation correction before OCR recognition.")
    parser.add_argument("--ocr-orientation-model", default="models/ocr_orientation_model.pth", help="Text-crop orientation correction model weights (.pth).")
    parser.add_argument("--ocr-orientation-device", help="Text-crop orientation correction device, e.g. cuda:0/cpu.")
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


def main() -> None:
    args = parse_args()
    output_json = Path(args.output_json)
    if not output_json.is_absolute():
        output_json = (Path.cwd() / output_json).resolve()
    ensure_dir(output_json.parent)

    vis_dir = None
    if args.vis_dir:
        vis_dir = Path(args.vis_dir)
        if not vis_dir.is_absolute():
            vis_dir = (Path.cwd() / vis_dir).resolve()
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
        fclip_device=args.fclip_device,
        fclip_model_config=args.fclip_config,
        fclip_params=args.fclip_params,
        fclip_threshold=args.fclip_threshold,
    )

    full_results = []
    delivery_results = []
    try:
        for image_path in tqdm(image_paths, desc="IQI Grade"):
            want_vis = vis_dir is not None
            full_record, artifacts = inferencer.infer_image_path(image_path, return_debug_artifacts=want_vis)
            full_results.append(full_record)
            delivery_results.append(build_delivery_record(full_record))

            if want_vis and artifacts is not None and artifacts.get("image") is not None:
                rel_path = _get_rel_path(image_path, image_root).with_suffix("")
                sample_dir = vis_dir / str(full_record.get("result_name", "unknown")) / rel_path
                save_debug_visualizations(
                    output_dir=vis_dir,
                    sample_dir=sample_dir,
                    image=artifacts["image"],
                    full_ocr_result=full_record.get("full_image_ocr") or full_record.get("ocr") or {},
                    full_ocr_image=artifacts.get("full_ocr_input"),
                    roi_info=full_record.get("roi") or {},
                    roi_image=artifacts.get("roi_image"),
                    roi_gray=artifacts.get("roi_gray"),
                    roi_ocr_result=full_record.get("roi_ocr") or {},
                    wire_result=full_record.get("wire") or {},
                )
    finally:
        inferencer.close()

    summary = build_iqi_statistics(full_results, topk=args.ocr_topk)
    payload = {
        "schema": "iqi_grade_batch_v1",
        "ok": True,
        "fatal_error": None,
        "meta": {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "image_root": str(image_root) if image_root is not None else None,
            "supported_exts": list(SUPPORTED_IMAGE_EXTS),
            **inferencer.get_runtime_meta(),
            "ocr_device": args.ocr_device,
            "ocr_det_model_name": args.ocr_det_model_name,
            "ocr_det_model_dir": args.ocr_det_model_dir,
            "ocr_rec_model_name": args.ocr_rec_model_name,
            "ocr_rec_model_dir": args.ocr_rec_model_dir,
            "ocr_det_limit_side_len": args.ocr_det_limit_side_len,
            "ocr_det_limit_type": args.ocr_det_limit_type,
            "ocr_number_range": args.ocr_number_range,
            "enable_ocr_orientation": args.enable_ocr_orientation,
            "ocr_orientation_model": args.ocr_orientation_model,
            "ocr_orientation_device": args.ocr_orientation_device,
            "vis_dir": str(vis_dir) if vis_dir is not None else None,
        },
        "summary": {
            "images_total": summary["images_total"],
            "success_total": summary["success_total"],
            "failure_total": summary["failure_total"],
            "result_code_hist": summary["result_code_hist"],
            "result_code_hist_named": summary["result_code_hist_named"],
            "iqi_type_hist": summary["iqi_type_hist"],
            "grade_hist": summary["grade_hist"],
            "field_totals": summary["field_totals"],
            "images_with_general_fields": summary["images_with_general_fields"],
            "images_with_iqi_marker": summary["images_with_iqi_marker"],
        },
        "results": delivery_results,
    }

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(_to_jsonable(payload), f, indent=2, ensure_ascii=False)

    print(f"\nIQI grade 推理完成，共处理 {len(delivery_results)} 张图像。")
    print(f"输出JSON: {output_json}")


if __name__ == "__main__":
    main()
