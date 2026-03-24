#!/usr/bin/env python3
"""Export text-detection crops directly from source images for OCR labeling."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

try:
    from common import get_default_dataset_root, make_sample_id, write_jsonl
except ModuleNotFoundError:  # pragma: no cover - import fallback for module execution
    from OCRtrain.scripts.common import get_default_dataset_root, make_sample_id, write_jsonl
from gauge.pipeline_utils import (
    collect_images,
    crop_rotated_polygon,
    enhance_windowing_gray,
    ensure_dir,
    load_image,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PaddleOCR TextDetection directly on source images and export text crops."
    )
    parser.add_argument(
        "--dataset-root",
        default=str(get_default_dataset_root()),
        help="Output dataset root.",
    )
    parser.add_argument(
        "--image-root",
        action="append",
        required=True,
        help="Source image root. Repeat the argument or pass comma-separated paths.",
    )
    parser.add_argument(
        "--enhance-mode",
        choices=["original", "windowing"],
        default="windowing",
        help="Preprocess mode used before TextDetection and crop export.",
    )
    parser.add_argument(
        "--text-det-device",
        choices=["cpu", "gpu"],
        default="gpu",
        help="PaddleOCR TextDetection device.",
    )
    parser.add_argument(
        "--text-det-model-name",
        default="PP-OCRv5_server_det",
        help="PaddleOCR TextDetection model name.",
    )
    parser.add_argument("--text-det-model-dir", help="Optional local TextDetection model directory.")
    parser.add_argument("--text-det-thresh", type=float, help="Override text detection thresh.")
    parser.add_argument("--text-det-box-thresh", type=float, help="Override text detection box thresh.")
    parser.add_argument("--text-det-unclip-ratio", type=float, help="Override text detection unclip ratio.")
    parser.add_argument("--min-crop-side", type=int, default=8, help="Minimum crop width/height.")
    parser.add_argument("--max-images", type=int, help="Optional max images after sampling.")
    parser.add_argument(
        "--sample-ratio",
        type=float,
        default=1.0,
        help="Randomly sample this ratio of collected source images. 1.0 means process all images.",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=20260315,
        help="Random seed used with --sample-ratio for reproducible sampling.",
    )
    parser.add_argument("--vis", action="store_true", help="Save text detection visualizations.")
    return parser.parse_args()


def create_text_detector(model_name: str, model_dir: Optional[str], device: str):
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import TextDetection

    kwargs: Dict[str, Any] = {"device": device}
    if model_name:
        kwargs["model_name"] = model_name
    if model_dir:
        kwargs["model_dir"] = model_dir
    return TextDetection(**kwargs)


def normalize_text_det_output(result: Any) -> Dict[str, Any]:
    if isinstance(result, list):
        if not result:
            return {"dt_polys": [], "dt_scores": []}
        result = result[0]
    if hasattr(result, "keys"):
        dt_polys = result.get("dt_polys")
        dt_scores = result.get("dt_scores")
        if dt_polys is None:
            dt_polys_list: List[Any] = []
        elif isinstance(dt_polys, np.ndarray):
            dt_polys_list = dt_polys.tolist()
        else:
            dt_polys_list = list(dt_polys)

        if dt_scores is None:
            dt_scores_list: List[Any] = []
        elif isinstance(dt_scores, np.ndarray):
            dt_scores_list = dt_scores.tolist()
        else:
            dt_scores_list = list(dt_scores)
        return {"dt_polys": dt_polys_list, "dt_scores": dt_scores_list}
    return {"dt_polys": [], "dt_scores": []}


def draw_text_polys(image: np.ndarray, polys: List[Any]) -> np.ndarray:
    vis = image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    for poly in polys:
        pts = np.array(poly, dtype=np.float32).reshape(-1, 1, 2).astype(np.int32)
        cv2.polylines(vis, [pts], True, (0, 0, 255), 2)
    return vis


def split_image_roots(raw_values: List[str]) -> List[Path]:
    roots: List[Path] = []
    for raw in raw_values:
        for part in str(raw).split(","):
            item = part.strip()
            if not item:
                continue
            path = Path(item).expanduser().resolve()
            if not path.is_dir():
                raise NotADirectoryError(path)
            roots.append(path)
    if not roots:
        raise ValueError("At least one valid --image-root is required.")
    return roots


def clean_token(value: str) -> str:
    out = []
    for ch in str(value):
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    cleaned = "".join(out).strip("_")
    return cleaned or "root"


def build_root_aliases(image_roots: List[Path]) -> Dict[Path, str]:
    aliases: Dict[Path, str] = {}
    used = set()
    for root in image_roots:
        base = clean_token(root.name)
        digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:6]
        alias = f"{base}__{digest}"
        while alias in used:
            digest = hashlib.sha1(f"{root}:{alias}".encode("utf-8")).hexdigest()[:6]
            alias = f"{base}__{digest}"
        used.add(alias)
        aliases[root] = alias
    return aliases


def collect_source_records(image_roots: List[Path]) -> List[Dict[str, Any]]:
    aliases = build_root_aliases(image_roots)
    records: List[Dict[str, Any]] = []
    for root in image_roots:
        for image_path in collect_images(root, None, None):
            rel_path = image_path.relative_to(root)
            records.append(
                {
                    "source_root": str(root),
                    "source_root_alias": aliases[root],
                    "source_image_path": str(image_path),
                    "source_relative_path": str(rel_path),
                }
            )
    if not records:
        raise FileNotFoundError("No supported images were found under the provided --image-root directories.")
    return records


def select_source_records(
    rows: List[Dict[str, Any]],
    sample_ratio: float,
    sample_seed: int,
    max_images: Optional[int],
) -> List[Dict[str, Any]]:
    if not 0 < sample_ratio <= 1:
        raise ValueError("--sample-ratio must be in the range (0, 1].")

    selected = list(rows)
    if sample_ratio < 1.0:
        sample_count = max(1, int(round(len(rows) * sample_ratio)))
        sample_count = min(sample_count, len(rows))
        rng = random.Random(sample_seed)
        selected = [rows[idx] for idx in sorted(rng.sample(range(len(rows)), sample_count))]

    if max_images is not None:
        selected = selected[:max_images]
    return selected


def build_detection_image(image: np.ndarray, enhance_mode: str) -> np.ndarray:
    if enhance_mode == "windowing":
        return enhance_windowing_gray(image)
    return image


def build_detector_input(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def export_crops(args: argparse.Namespace) -> Dict[str, int]:
    dataset_root = Path(args.dataset_root).resolve()
    manifests_root = dataset_root / "manifests"
    ensure_dir(manifests_root)

    image_roots = split_image_roots(args.image_root)
    source_records_all = collect_source_records(image_roots)
    source_records = select_source_records(
        source_records_all,
        sample_ratio=args.sample_ratio,
        sample_seed=args.sample_seed,
        max_images=args.max_images,
    )

    text_detector = create_text_detector(
        model_name=args.text_det_model_name,
        model_dir=args.text_det_model_dir,
        device=args.text_det_device,
    )

    source_rows: List[Dict[str, Any]] = []
    crop_rows: List[Dict[str, Any]] = []
    error_rows: List[Dict[str, Any]] = []
    stats = {
        "source_images_total": len(source_records_all),
        "images_total": len(source_records),
        "text_det_ok": 0,
        "text_det_empty": 0,
        "crop_saved": 0,
        "error": 0,
    }

    for row in source_records:
        image_path = Path(row["source_image_path"])
        rel_path = Path(row["source_relative_path"])
        root_alias = str(row["source_root_alias"])
        base_row = {
            "source_root": row["source_root"],
            "source_root_alias": root_alias,
            "source_image_path": row["source_image_path"],
            "source_relative_path": row["source_relative_path"],
        }
        try:
            image = load_image(image_path)
            det_image = build_detection_image(image, args.enhance_mode)
            det_output = normalize_text_det_output(
                text_detector.predict(
                    build_detector_input(det_image),
                    thresh=args.text_det_thresh,
                    box_thresh=args.text_det_box_thresh,
                    unclip_ratio=args.text_det_unclip_ratio,
                )
            )
            dt_polys = det_output["dt_polys"]
            dt_scores = det_output["dt_scores"]

            source_row = {
                **base_row,
                "status": "ok" if dt_polys else "no_text",
                "enhance_mode": args.enhance_mode,
                "image_size": [int(image.shape[1]), int(image.shape[0])],
                "det_box_count": len(dt_polys),
            }

            if args.vis:
                vis_rel_path = Path("vis/text_det/all") / root_alias / rel_path.with_suffix(".png")
                vis_abs_path = dataset_root / vis_rel_path
                ensure_dir(vis_abs_path.parent)
                cv2.imwrite(str(vis_abs_path), draw_text_polys(det_image, dt_polys))
                source_row["text_det_vis_relative_path"] = str(vis_rel_path)

            if not dt_polys:
                stats["text_det_empty"] += 1
                source_rows.append(source_row)
                continue

            stats["text_det_ok"] += 1
            saved_for_image = 0
            for idx, poly in enumerate(dt_polys):
                poly_np = np.array(poly, dtype=np.float32).reshape(-1, 2)
                crop, _ = crop_rotated_polygon(det_image, poly_np)
                if crop is None:
                    continue
                h, w = crop.shape[:2]
                if min(h, w) < args.min_crop_side:
                    continue

                sample_id = make_sample_id(root_alias, str(rel_path.with_suffix("")), f"det_{idx:03d}")
                crop_rel_path = Path("det_crops/all") / root_alias / rel_path.with_suffix("") / f"{sample_id}.png"
                crop_abs_path = dataset_root / crop_rel_path
                ensure_dir(crop_abs_path.parent)
                cv2.imwrite(str(crop_abs_path), crop)

                stats["crop_saved"] += 1
                saved_for_image += 1
                crop_rows.append(
                    {
                        **base_row,
                        "sample_id": sample_id,
                        "status": "ok",
                        "crop_index": idx,
                        "crop_relative_path": str(crop_rel_path),
                        "polygon": poly_np.tolist(),
                        "score": float(dt_scores[idx]) if idx < len(dt_scores) else None,
                        "crop_size": [int(w), int(h)],
                        "image_size": [int(image.shape[1]), int(image.shape[0])],
                        "enhance_mode": args.enhance_mode,
                    }
                )

            source_row["crop_saved"] = saved_for_image
            source_rows.append(source_row)
        except Exception as exc:
            stats["error"] += 1
            error_rows.append({**base_row, "status": "error", "error": str(exc)})

    write_jsonl(manifests_root / "source_images_all.jsonl", source_rows)
    write_jsonl(manifests_root / "crops_all.jsonl", crop_rows)
    write_jsonl(manifests_root / "errors_text_det_all.jsonl", error_rows)

    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
    (manifests_root / "export_text_crops_stats.json").write_text(stats_json, encoding="utf-8")
    (manifests_root / "export_text_crops_text_det_stats.json").write_text(stats_json, encoding="utf-8")
    return stats


def main() -> None:
    args = parse_args()
    stats = export_crops(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
