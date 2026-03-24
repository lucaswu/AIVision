#!/usr/bin/env python3
"""Convert manual crop transcriptions into PaddleOCR recognition dataset files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from common import get_default_dataset_root, load_label_tsv, read_jsonl


PRESET_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_/.:()[] "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PaddleOCR recognition label files.")
    parser.add_argument(
        "--dataset-root",
        default=str(get_default_dataset_root()),
        help="Dataset root under local/OCRdatasets.",
    )
    parser.add_argument("--train-manifest", help="Train crop manifest JSONL.")
    parser.add_argument("--val-manifest", help="Val crop manifest JSONL.")
    parser.add_argument("--train-labels", help="Train transcription TSV.")
    parser.add_argument("--val-labels", help="Val transcription TSV.")
    parser.add_argument(
        "--output-dir",
        help="Directory to place train.txt/val.txt/dict.txt. Defaults to <dataset-root>/rec_dataset.",
    )
    parser.add_argument(
        "--dict-mode",
        choices=["preset_plus_labels", "labels_only"],
        default="preset_plus_labels",
        help="How to build dict.txt.",
    )
    parser.add_argument("--drop-empty", action="store_true", help="Drop empty labels.")
    return parser.parse_args()


def load_manifest_map(path: Path) -> Dict[str, Dict]:
    items: Dict[str, Dict] = {}
    for row in read_jsonl(path):
        if row.get("status") != "ok":
            continue
        sample_id = row.get("sample_id")
        if sample_id:
            items[sample_id] = row
    return items


def build_lines(
    manifest_map: Dict[str, Dict],
    labels: Dict[str, Dict[str, str]],
    dataset_root: Path,
    *,
    drop_empty: bool,
) -> List[str]:
    lines: List[str] = []
    for sample_id, meta in manifest_map.items():
        label = labels.get(sample_id)
        if not label or label.get("status") != "ok":
            continue
        text = label.get("text", "")
        if drop_empty and not text:
            continue
        crop_rel_path = meta["crop_relative_path"]
        lines.append(f"{crop_rel_path}\t{text}")
    return lines


def collect_chars(lines: Sequence[str], dict_mode: str) -> List[str]:
    chars: List[str] = []
    seen = set()

    def add(char: str) -> None:
        if char in seen:
            return
        seen.add(char)
        chars.append(char)

    if dict_mode == "preset_plus_labels":
        for char in PRESET_CHARS:
            add(char)

    for line in lines:
        text = line.split("\t", 1)[1] if "\t" in line else ""
        for char in text:
            add(char)
    return chars


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else dataset_root / "rec_dataset"

    train_manifest = Path(args.train_manifest).resolve() if args.train_manifest else dataset_root / "manifests" / "crops_train.jsonl"
    val_manifest = Path(args.val_manifest).resolve() if args.val_manifest else dataset_root / "manifests" / "crops_val.jsonl"
    train_labels = Path(args.train_labels).resolve() if args.train_labels else dataset_root / "annotations" / "crops_train_labels.tsv"
    val_labels = Path(args.val_labels).resolve() if args.val_labels else dataset_root / "annotations" / "crops_val_labels.tsv"

    output_dir.mkdir(parents=True, exist_ok=True)

    train_manifest_map = load_manifest_map(train_manifest)
    val_manifest_map = load_manifest_map(val_manifest)
    train_label_map = load_label_tsv(train_labels)
    val_label_map = load_label_tsv(val_labels)

    train_lines = build_lines(train_manifest_map, train_label_map, dataset_root, drop_empty=args.drop_empty)
    val_lines = build_lines(val_manifest_map, val_label_map, dataset_root, drop_empty=args.drop_empty)
    dict_chars = collect_chars(train_lines + val_lines, args.dict_mode)

    (output_dir / "train.txt").write_text("\n".join(train_lines) + ("\n" if train_lines else ""), encoding="utf-8")
    (output_dir / "val.txt").write_text("\n".join(val_lines) + ("\n" if val_lines else ""), encoding="utf-8")
    with (output_dir / "dict.txt").open("w", encoding="utf-8") as f:
        for char in dict_chars:
            f.write(f"{char}\n")

    meta = {
        "dataset_root": str(dataset_root),
        "output_dir": str(output_dir),
        "train_manifest": str(train_manifest),
        "val_manifest": str(val_manifest),
        "train_labels": str(train_labels),
        "val_labels": str(val_labels),
        "train_samples": len(train_lines),
        "val_samples": len(val_lines),
        "dict_size": len(dict_chars),
        "dict_mode": args.dict_mode,
        "drop_empty": args.drop_empty,
    }
    (output_dir / "build_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
