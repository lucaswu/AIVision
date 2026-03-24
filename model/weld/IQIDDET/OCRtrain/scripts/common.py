#!/usr/bin/env python3
"""Common helpers for the OCRtrain workflow."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, Iterator, List


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, rows: Iterable[Dict]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> Iterator[Dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def symlink_file(src: Path, dst: Path, *, force: bool = False) -> None:
    ensure_dir(dst.parent)
    if dst.exists() or dst.is_symlink():
        if not force:
            return
        if dst.is_dir() and not dst.is_symlink():
            raise IsADirectoryError(dst)
        dst.unlink()
    dst.symlink_to(src.resolve())


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path.resolve().relative_to(root.resolve()))


def make_sample_id(*parts: str) -> str:
    raw = "::".join(parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    cleaned = "__".join(_clean_token(part) for part in parts if part)
    cleaned = cleaned[:120].strip("_") or "sample"
    return f"{cleaned}__{digest}"


def _clean_token(value: str) -> str:
    out = []
    for ch in str(value):
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def get_default_dataset_root() -> Path:
    return REPO_ROOT / "local" / "OCRdatasets" / "iqi_rec_v1"


def getenv_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    return Path(value).expanduser().resolve()


def load_label_tsv(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    records: Dict[str, Dict[str, str]] = {}
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.rstrip("\n")
            if not line:
                continue
            if idx == 0 and line.startswith("sample_id\t"):
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            sample_id, text, status, crop_rel_path = parts[:4]
            records[sample_id] = {
                "sample_id": sample_id,
                "text": text,
                "status": status,
                "crop_rel_path": crop_rel_path,
            }
    return records


def write_label_tsv(path: Path, rows: List[Dict[str, str]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        f.write("sample_id\ttext\tstatus\tcrop_rel_path\n")
        for row in rows:
            f.write(
                "\t".join(
                    [
                        row.get("sample_id", ""),
                        row.get("text", ""),
                        row.get("status", ""),
                        row.get("crop_rel_path", ""),
                    ]
                )
                + "\n"
            )
