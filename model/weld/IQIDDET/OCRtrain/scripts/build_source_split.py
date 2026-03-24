#!/usr/bin/env python3
"""Create a train/val source split with symlinks for OCR recognition training."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from common import get_default_dataset_root, relative_to_root, symlink_file, write_jsonl
from gauge.pipeline_utils import collect_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a source image split for OCR training.")
    parser.add_argument(
        "--image-dir",
        default="IQIdata/ori/img",
        help="Directory containing original source images.",
    )
    parser.add_argument(
        "--output-root",
        default=str(get_default_dataset_root()),
        help="Dataset root under local/OCRdatasets.",
    )
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio.")
    parser.add_argument("--seed", type=int, default=20260315, help="Random seed.")
    parser.add_argument(
        "--group-regex",
        help="Optional regex with one capture group. Images sharing the same group key stay in the same split.",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing symlinks and manifests.")
    return parser.parse_args()


def build_group_key(rel_path: Path, group_regex: Optional[str]) -> str:
    if not group_regex:
        return str(rel_path)
    import re

    match = re.search(group_regex, rel_path.stem)
    if match and match.groups():
        return match.group(1)
    return str(rel_path)


def main() -> None:
    args = parse_args()
    image_dir = Path(args.image_dir).resolve()
    output_root = Path(args.output_root).resolve()
    source_root = output_root / "source"
    manifests_root = output_root / "manifests"

    images = collect_images(image_dir=image_dir, image_list=None)
    groups: Dict[str, List[Path]] = {}
    for path in images:
        rel_path = path.relative_to(image_dir)
        key = build_group_key(rel_path, args.group_regex)
        groups.setdefault(key, []).append(path)

    keys = list(groups.keys())
    rng = random.Random(args.seed)
    rng.shuffle(keys)
    val_target = max(1, int(round(len(images) * args.val_ratio)))
    val_count = 0
    train_paths: List[Path] = []
    val_paths: List[Path] = []

    for key in keys:
        bucket = groups[key]
        if val_count < val_target:
            val_paths.extend(bucket)
            val_count += len(bucket)
        else:
            train_paths.extend(bucket)

    if not train_paths:
        raise RuntimeError("Train split is empty. Reduce val_ratio or adjust grouping.")

    records = {"train": train_paths, "val": val_paths}
    for subset, paths in records.items():
        subset_dir = source_root / f"{subset}_images"
        lines = []
        jsonl_rows = []
        for src in paths:
            rel_path = src.relative_to(image_dir)
            dst = subset_dir / rel_path
            symlink_file(src, dst, force=args.force)
            rel_from_dataset = relative_to_root(dst, output_root)
            lines.append(rel_from_dataset)
            jsonl_rows.append(
                {
                    "subset": subset,
                    "source_path": str(src),
                    "relative_path": str(rel_path),
                    "symlink_path": rel_from_dataset,
                    "group_key": build_group_key(rel_path, args.group_regex),
                }
            )

        list_path = manifests_root / f"source_{subset}.txt"
        list_path.parent.mkdir(parents=True, exist_ok=True)
        list_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        write_jsonl(manifests_root / f"source_{subset}.jsonl", jsonl_rows)

    meta = {
        "image_dir": str(image_dir),
        "output_root": str(output_root),
        "images_total": len(images),
        "train_images": len(train_paths),
        "val_images": len(val_paths),
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "group_regex": args.group_regex,
    }
    (manifests_root / "split_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
