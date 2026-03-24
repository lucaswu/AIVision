#!/usr/bin/env python3
"""Merge multiple no-box OCR label files into one flat PaddleOCR dataset."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from common import ensure_dir, make_sample_id, write_jsonl
except ImportError:
    from OCRtrain.scripts.common import ensure_dir, make_sample_id, write_jsonl


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "IQIdata" / "OCRdata" / "0320" / "all"
DEFAULT_SOURCES = [
    {
        "name": "labeled1",
        "label_file": REPO_ROOT / "local" / "OCRdatasets" / "0320" / "labeled1" / "iqi_rec_textdet_v1.txt",
        "image_root": REPO_ROOT / "local" / "OCRdatasets" / "0320" / "labeled1" / "iqi_rec_textdet_v1",
    },
    {
        "name": "labeled2",
        "label_file": REPO_ROOT / "local" / "OCRdatasets" / "0320" / "labeled2" / "train.txt",
        "image_root": REPO_ROOT / "local" / "OCRdatasets" / "0320" / "labeled2",
    },
]
MANAGED_FILES = [
    "train.txt",
    "val.txt",
    "dict.txt",
    "merge_meta.json",
    "merge_errors.jsonl",
    "merge_records.jsonl",
]


@dataclass
class SourceSpec:
    name: str
    label_file: Path
    image_root: Path


@dataclass
class SampleRecord:
    source_name: str
    label_file: Path
    line_no: int
    source_rel_path: str
    source_image_path: Path
    text: str
    output_name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge multiple label_rec_no_box outputs into one flat PaddleOCR dataset.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help=(
            "Optional custom source in the form "
            "'name=/path/to/labels.txt::/path/to/image_root'. "
            "Repeat this flag to provide multiple sources. If omitted, built-in defaults are used."
        ),
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Output dataset root. Defaults to IQIdata/OCRdata/0320/all.",
    )
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio. Default: 0.1")
    parser.add_argument("--seed", type=int, default=20260320, help="Random seed for train/val split.")
    parser.add_argument(
        "--allow-empty-label",
        action="store_true",
        help="Keep rows whose label text is empty after stripping. Disabled by default.",
    )
    return parser.parse_args()


def parse_source_specs(raw_sources: Sequence[str]) -> List[SourceSpec]:
    if not raw_sources:
        return [
            SourceSpec(
                name=item["name"],
                label_file=Path(item["label_file"]).resolve(),
                image_root=Path(item["image_root"]).resolve(),
            )
            for item in DEFAULT_SOURCES
        ]

    specs: List[SourceSpec] = []
    for raw in raw_sources:
        if "=" not in raw or "::" not in raw:
            raise ValueError(
                f"Invalid --source value: {raw}. Expected name=/path/to/labels.txt::/path/to/image_root"
            )
        name, payload = raw.split("=", 1)
        label_file, image_root = payload.split("::", 1)
        specs.append(
            SourceSpec(
                name=name.strip(),
                label_file=Path(label_file).expanduser().resolve(),
                image_root=Path(image_root).expanduser().resolve(),
            )
        )
    return specs


def normalize_rel_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def parse_label_line(line: str) -> Tuple[str, str]:
    if "\t" not in line:
        raise ValueError("missing_tab")
    rel_path, text = line.split("\t", 1)
    rel_path = normalize_rel_path(rel_path)
    text = text.strip()
    if not rel_path:
        raise ValueError("empty_path")
    return rel_path, text


def collect_samples(
    sources: Sequence[SourceSpec],
    *,
    allow_empty_label: bool,
) -> Tuple[List[SampleRecord], List[Dict[str, object]]]:
    samples: List[SampleRecord] = []
    errors: List[Dict[str, object]] = []

    for spec in sources:
        if not spec.label_file.exists():
            errors.append(
                {
                    "source_name": spec.name,
                    "label_file": str(spec.label_file),
                    "line_no": 0,
                    "error": "label_file_missing",
                }
            )
            continue
        if not spec.image_root.exists():
            errors.append(
                {
                    "source_name": spec.name,
                    "label_file": str(spec.label_file),
                    "line_no": 0,
                    "error": "image_root_missing",
                    "image_root": str(spec.image_root),
                }
            )
            continue

        with spec.label_file.open("r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue

                try:
                    rel_path, text = parse_label_line(line)
                except ValueError as exc:
                    errors.append(
                        {
                            "source_name": spec.name,
                            "label_file": str(spec.label_file),
                            "line_no": line_no,
                            "error": str(exc),
                            "raw_line": line,
                        }
                    )
                    continue

                if not allow_empty_label and not text:
                    errors.append(
                        {
                            "source_name": spec.name,
                            "label_file": str(spec.label_file),
                            "line_no": line_no,
                            "error": "empty_label",
                            "relative_path": rel_path,
                        }
                    )
                    continue

                source_image_path = spec.image_root / Path(rel_path)
                if not source_image_path.exists():
                    errors.append(
                        {
                            "source_name": spec.name,
                            "label_file": str(spec.label_file),
                            "line_no": line_no,
                            "error": "source_image_missing",
                            "relative_path": rel_path,
                            "source_image_path": str(source_image_path),
                        }
                    )
                    continue

                suffix = source_image_path.suffix.lower() or ".png"
                rel_without_suffix = str(Path(rel_path).with_suffix(""))
                output_name = f"{make_sample_id(spec.name, rel_without_suffix)}{suffix}"
                samples.append(
                    SampleRecord(
                        source_name=spec.name,
                        label_file=spec.label_file,
                        line_no=line_no,
                        source_rel_path=rel_path,
                        source_image_path=source_image_path,
                        text=text,
                        output_name=output_name,
                    )
                )

    return samples, errors


def split_samples(samples: Sequence[SampleRecord], *, val_ratio: float, seed: int) -> Tuple[List[SampleRecord], List[SampleRecord]]:
    if not samples:
        return [], []
    items = list(samples)
    rng = random.Random(seed)
    rng.shuffle(items)
    if len(items) == 1:
        return items, []

    val_count = int(round(len(items) * val_ratio))
    val_count = max(1, min(len(items) - 1, val_count))
    val_samples = items[:val_count]
    train_samples = items[val_count:]
    return train_samples, val_samples


def build_label_lines(samples: Iterable[SampleRecord], subset: str) -> List[str]:
    return [f"images/{subset}/{row.output_name}\t{row.text}" for row in samples]


def build_dict_chars(lines: Sequence[str]) -> List[str]:
    return sorted({char for line in lines for char in line.split("\t", 1)[1]})


def reset_output(output_root: Path) -> None:
    images_root = output_root / "images"
    if images_root.exists():
        shutil.rmtree(images_root)
    ensure_dir(output_root / "images" / "train")
    ensure_dir(output_root / "images" / "val")
    for name in MANAGED_FILES:
        path = output_root / name
        if path.exists():
            path.unlink()


def copy_samples(samples: Iterable[SampleRecord], images_root: Path) -> None:
    for row in samples:
        shutil.copy2(row.source_image_path, images_root / row.output_name)


def sample_to_meta(row: SampleRecord, subset: str) -> Dict[str, object]:
    return {
        "subset": subset,
        "source_name": row.source_name,
        "label_file": str(row.label_file),
        "line_no": row.line_no,
        "source_rel_path": row.source_rel_path,
        "source_image_path": str(row.source_image_path),
        "output_name": row.output_name,
        "output_rel_path": f"images/{subset}/{row.output_name}",
        "text": row.text,
    }


def main() -> None:
    args = parse_args()
    if not 0.0 < args.val_ratio < 1.0:
        raise ValueError(f"--val-ratio must be between 0 and 1, got {args.val_ratio}")

    output_root = Path(args.output_root).expanduser().resolve()
    train_images_root = output_root / "images" / "train"
    val_images_root = output_root / "images" / "val"
    ensure_dir(output_root)
    sources = parse_source_specs(args.source)

    samples, errors = collect_samples(sources, allow_empty_label=args.allow_empty_label)
    train_samples, val_samples = split_samples(samples, val_ratio=args.val_ratio, seed=args.seed)

    reset_output(output_root)
    copy_samples(train_samples, train_images_root)
    copy_samples(val_samples, val_images_root)

    train_lines = build_label_lines(train_samples, "train")
    val_lines = build_label_lines(val_samples, "val")
    dict_chars = build_dict_chars(train_lines + val_lines)

    (output_root / "train.txt").write_text(
        "\n".join(train_lines) + ("\n" if train_lines else ""),
        encoding="utf-8",
    )
    (output_root / "val.txt").write_text(
        "\n".join(val_lines) + ("\n" if val_lines else ""),
        encoding="utf-8",
    )
    with (output_root / "dict.txt").open("w", encoding="utf-8") as f:
        for char in dict_chars:
            f.write(f"{char}\n")

    write_jsonl(output_root / "merge_errors.jsonl", errors)
    write_jsonl(
        output_root / "merge_records.jsonl",
        [sample_to_meta(row, "train") for row in train_samples]
        + [sample_to_meta(row, "val") for row in val_samples],
    )

    meta = {
        "output_root": str(output_root),
        "train_images_root": str(train_images_root),
        "val_images_root": str(val_images_root),
        "sources": [
            {
                "name": item.name,
                "label_file": str(item.label_file),
                "image_root": str(item.image_root),
            }
            for item in sources
        ],
        "samples_merged": len(samples),
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "dict_size": len(dict_chars),
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "allow_empty_label": args.allow_empty_label,
        "errors": len(errors),
    }
    (output_root / "merge_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
