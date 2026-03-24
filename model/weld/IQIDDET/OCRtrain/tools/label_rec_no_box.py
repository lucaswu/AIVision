#!/usr/bin/env python3
"""无检测框文本识别标注工具，支持图像矫正与直接写回 crop。"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import shutil
import sys
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import parse_qs, quote, urlencode, urlparse

from PIL import Image, ImageOps


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
BACKUP_DIR_NAME = ".label_backup"
STATUS_OK = "ok"
STATUS_SKIP = "skip"
STATUS_PENDING = "pending"
REJECT_TEXT = "~"
TRANSPOSE = getattr(Image, "Transpose", Image)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="启动无检测框 OCR 标注界面，支持旋转、镜像矫正并直接写回当前 crop。"
    )
    parser.add_argument("--image-dir", required=False, help="待标注文本图所在目录。不传时会弹窗选择。")
    parser.add_argument(
        "--output-file",
        default=None,
        help="PaddleOCR 格式标签文件输出路径。命令行模式默认写到 <image-dir>/../rec_gt.txt；弹窗模式默认写到 exe 当前目录。",
    )
    parser.add_argument(
        "--labels-tsv",
        default=None,
        help="用于断点续标和状态跟踪的 TSV 文件。默认与 output-file 同目录。",
    )
    parser.add_argument(
        "--path-root",
        default=None,
        help="写入 output-file 时用于生成相对路径的根目录。命令行模式默认使用 image-dir；弹窗模式会优先自动推断 det_crops 上级目录。",
    )
    parser.add_argument("--host", default="127.0.0.1", help="服务绑定地址。")
    parser.add_argument("--port", type=int, default=8766, help="服务端口。")
    return parser.parse_args()


def runtime_output_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def choose_image_dir_via_dialog() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on runtime
        raise RuntimeError("当前环境无法弹出目录选择框，请改用 --image-dir 显式传参。") from exc

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    selected = filedialog.askdirectory(title="请选择待标注图片目录")
    root.destroy()
    if not selected:
        return None
    return Path(selected).expanduser().resolve()


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value.strip())
    return cleaned.strip("._") or "rec_gt"


def infer_path_root(image_dir: Path) -> Path:
    for candidate in [image_dir] + list(image_dir.parents):
        if candidate.name == "det_crops":
            return candidate.parent
    return image_dir


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def canonicalize_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value == STATUS_OK:
        return STATUS_OK
    if value in {STATUS_SKIP, "unclear"}:
        return STATUS_SKIP
    return STATUS_PENDING


def normalize_text(text: str) -> str:
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def natural_key(value: str) -> List[object]:
    parts = re.split(r"(\d+)", value.lower())
    key: List[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return key


def resolve_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path.resolve())


def parse_rotate_k(value: str | int | None) -> int:
    try:
        return int(value or 0) % 4
    except (TypeError, ValueError):
        return 0


def parse_bool_flag(value: str | int | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def is_identity_transform(rotate_k: int, flip_horizontal: bool) -> bool:
    return parse_rotate_k(rotate_k) == 0 and not flip_horizontal


def apply_image_transform(image: Image.Image, rotate_k: int, flip_horizontal: bool) -> Image.Image:
    rotate_k = parse_rotate_k(rotate_k)
    transformed = image.copy()
    if rotate_k == 1:
        transformed = transformed.transpose(TRANSPOSE.ROTATE_270)
    elif rotate_k == 2:
        transformed = transformed.transpose(TRANSPOSE.ROTATE_180)
    elif rotate_k == 3:
        transformed = transformed.transpose(TRANSPOSE.ROTATE_90)
    if flip_horizontal:
        transformed = ImageOps.mirror(transformed)
    return transformed


def compose_transforms(
    total_rotate_k: int,
    total_flip_horizontal: bool,
    delta_rotate_k: int,
    delta_flip_horizontal: bool,
) -> Tuple[int, bool]:
    total_rotate_k = parse_rotate_k(total_rotate_k)
    delta_rotate_k = parse_rotate_k(delta_rotate_k)
    sign = -1 if total_flip_horizontal else 1
    new_rotate_k = (sign * delta_rotate_k + total_rotate_k) % 4
    new_flip_horizontal = bool(total_flip_horizontal) ^ bool(delta_flip_horizontal)
    return new_rotate_k, new_flip_horizontal


def save_image_to_path(image: Image.Image, path: Path) -> None:
    to_save = image
    if path.suffix.lower() in {".jpg", ".jpeg"} and to_save.mode not in {"RGB", "L"}:
        to_save = to_save.convert("RGB")
    ensure_dir(path.parent)
    to_save.save(path)


def scan_images(image_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in sorted(
        image_dir.rglob("*"),
        key=lambda item: natural_key(str(item.relative_to(image_dir))),
    ):
        if not path.is_file():
            continue
        if BACKUP_DIR_NAME in path.parts:
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        rows.append({"image_rel_path": str(path.relative_to(image_dir))})
    if not rows:
        raise RuntimeError(f"No images found under {image_dir}")
    return rows


def load_labels_tsv(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    labels: Dict[str, Dict[str, object]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            image_rel_path = row.get("image_rel_path", "").strip()
            if not image_rel_path:
                continue
            labels[image_rel_path] = {
                "image_rel_path": image_rel_path,
                "export_path": row.get("export_path", "").strip(),
                "text": row.get("text", ""),
                "status": canonicalize_status(row.get("status", "")),
                "updated_at": row.get("updated_at", "").strip(),
                "total_rotate_k": parse_rotate_k(row.get("total_rotate_k", "0")),
                "total_flip_horizontal": parse_bool_flag(row.get("total_flip_horizontal", "0")),
                "image_updated": parse_bool_flag(row.get("image_updated", "0")),
            }
    return labels


def load_rec_gt(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    labels: Dict[str, Dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or "\t" not in line:
                continue
            export_path, text = line.split("\t", 1)
            labels[export_path] = {
                "export_path": export_path,
                "text": text,
                "status": STATUS_OK,
                "total_rotate_k": 0,
                "total_flip_horizontal": False,
                "image_updated": False,
            }
    return labels


def write_labels_tsv(path: Path, rows: Iterable[Dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "image_rel_path",
                "export_path",
                "text",
                "status",
                "updated_at",
                "total_rotate_k",
                "total_flip_horizontal",
                "image_updated",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "image_rel_path": row.get("image_rel_path", ""),
                    "export_path": row.get("export_path", ""),
                    "text": row.get("text", ""),
                    "status": canonicalize_status(str(row.get("status", ""))),
                    "updated_at": row.get("updated_at", ""),
                    "total_rotate_k": parse_rotate_k(row.get("total_rotate_k", 0)),
                    "total_flip_horizontal": "1" if parse_bool_flag(row.get("total_flip_horizontal")) else "0",
                    "image_updated": "1" if parse_bool_flag(row.get("image_updated")) else "0",
                }
            )


def row_bucket(label: Dict[str, object] | None) -> str:
    if not label:
        return STATUS_PENDING
    status = canonicalize_status(str(label.get("status", "")))
    if status == STATUS_SKIP:
        return STATUS_SKIP
    if status != STATUS_OK:
        return STATUS_PENDING
    if normalize_text(str(label.get("text", ""))) == REJECT_TEXT:
        return "reject"
    return STATUS_OK


def bucket_icon(bucket: str) -> str:
    if bucket == STATUS_OK:
        return "&#10003;"
    if bucket == "reject":
        return "~"
    if bucket == STATUS_SKIP:
        return "&#10007;"
    return "&#9723;"


def bucket_label(bucket: str) -> str:
    if bucket == STATUS_OK:
        return "已标注"
    if bucket == "reject":
        return "拒识 (~)"
    if bucket == STATUS_SKIP:
        return "已跳过"
    return "待处理"


def safe_index(raw_value: str, total: int) -> int:
    try:
        index = int(raw_value)
    except (TypeError, ValueError):
        index = 0
    return max(0, min(index, total - 1))


def describe_transform(rotate_k: int, flip_horizontal: bool) -> str:
    rotate_k = parse_rotate_k(rotate_k)
    if is_identity_transform(rotate_k, flip_horizontal):
        return "无"
    parts = []
    if rotate_k:
        parts.append(f"顺时针旋转 {rotate_k * 90} 度")
    if flip_horizontal:
        parts.append("水平镜像")
    return " + ".join(parts)


class AppState:
    def __init__(
        self,
        image_dir: Path,
        path_root: Path,
        rows: List[Dict[str, str]],
        output_file: Path,
        labels_tsv: Path,
        session_file: Path,
    ):
        self.image_dir = image_dir
        self.path_root = path_root
        self.rows = rows
        self.output_file = output_file
        self.labels_tsv = labels_tsv
        self.session_file = session_file
        self.backup_dir = image_dir / BACKUP_DIR_NAME
        self.labels = self._load_existing_labels()
        self.index_by_rel_path = {
            row["image_rel_path"]: idx for idx, row in enumerate(self.rows)
        }
        self.session = self._load_session()

    def _load_existing_labels(self) -> Dict[str, Dict[str, object]]:
        labels = load_labels_tsv(self.labels_tsv)
        rec_gt = load_rec_gt(self.output_file)
        by_export = {row["export_path"]: row for row in self.rows}
        for export_path, item in rec_gt.items():
            row = by_export.get(export_path)
            if row is None:
                continue
            labels.setdefault(
                row["image_rel_path"],
                {
                    "image_rel_path": row["image_rel_path"],
                    "export_path": export_path,
                    "text": item.get("text", ""),
                    "status": STATUS_OK,
                    "updated_at": "",
                    "total_rotate_k": 0,
                    "total_flip_horizontal": False,
                    "image_updated": False,
                },
            )
        return labels

    def _session_config(self) -> Dict[str, str]:
        return {
            "image_dir": str(self.image_dir),
            "path_root": str(self.path_root),
            "output_file": str(self.output_file),
            "labels_tsv": str(self.labels_tsv),
        }

    def _load_session(self) -> Dict[str, str]:
        if not self.session_file.exists():
            return {}
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if data.get("config") != self._session_config():
            return {}
        return data

    def _write_session(self) -> None:
        ensure_dir(self.session_file.parent)
        payload = {
            "config": self._session_config(),
            "current_image_rel_path": self.session.get("current_image_rel_path", ""),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.session_file.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def remember_current(self, image_rel_path: str) -> None:
        self.session["current_image_rel_path"] = image_rel_path
        self._write_session()

    def row_status(self, image_rel_path: str) -> str:
        item = self.labels.get(image_rel_path)
        if not item:
            return STATUS_PENDING
        return canonicalize_status(str(item.get("status", "")))

    def row_bucket(self, image_rel_path: str) -> str:
        return row_bucket(self.labels.get(image_rel_path))

    def first_pending_index(self) -> int:
        for idx, row in enumerate(self.rows):
            if self.row_bucket(row["image_rel_path"]) == STATUS_PENDING:
                return idx
        return 0

    def resume_index(self) -> int:
        current_image_rel_path = self.session.get("current_image_rel_path", "")
        if current_image_rel_path in self.index_by_rel_path:
            return self.index_by_rel_path[current_image_rel_path]
        return self.first_pending_index()

    def get_label(self, image_rel_path: str) -> Dict[str, object]:
        return self.labels.get(image_rel_path, {})

    def get_image_path(self, image_rel_path: str) -> Path:
        return self.image_dir / image_rel_path

    def get_backup_path(self, image_rel_path: str) -> Path:
        return self.backup_dir / image_rel_path

    def get_saved_transform(self, image_rel_path: str) -> Tuple[int, bool, bool]:
        label = self.labels.get(image_rel_path, {})
        rotate_k = parse_rotate_k(label.get("total_rotate_k", 0))
        flip_horizontal = parse_bool_flag(label.get("total_flip_horizontal", False))
        image_updated = parse_bool_flag(label.get("image_updated", False))
        return rotate_k, flip_horizontal, image_updated

    def apply_image_update(
        self,
        image_rel_path: str,
        delta_rotate_k: int,
        delta_flip_horizontal: bool,
    ) -> Tuple[int, bool, bool]:
        saved_rotate_k, saved_flip_horizontal, saved_image_updated = self.get_saved_transform(image_rel_path)
        delta_rotate_k = parse_rotate_k(delta_rotate_k)
        delta_flip_horizontal = bool(delta_flip_horizontal)
        if is_identity_transform(delta_rotate_k, delta_flip_horizontal):
            return saved_rotate_k, saved_flip_horizontal, saved_image_updated

        image_path = self.get_image_path(image_rel_path)
        backup_path = self.get_backup_path(image_rel_path)
        if not backup_path.exists():
            ensure_dir(backup_path.parent)
            shutil.copy2(image_path, backup_path)

        total_rotate_k, total_flip_horizontal = compose_transforms(
            saved_rotate_k,
            saved_flip_horizontal,
            delta_rotate_k,
            delta_flip_horizontal,
        )
        with Image.open(backup_path) as original_image:
            transformed = apply_image_transform(original_image, total_rotate_k, total_flip_horizontal)
            save_image_to_path(transformed, image_path)

        image_updated = not is_identity_transform(total_rotate_k, total_flip_horizontal)
        return total_rotate_k, total_flip_horizontal, image_updated

    def save_label(
        self,
        image_rel_path: str,
        text: str,
        status: str,
        delta_rotate_k: int,
        delta_flip_horizontal: bool,
    ) -> None:
        row = self.rows[self.index_by_rel_path[image_rel_path]]
        total_rotate_k, total_flip_horizontal, image_updated = self.apply_image_update(
            image_rel_path=image_rel_path,
            delta_rotate_k=delta_rotate_k,
            delta_flip_horizontal=delta_flip_horizontal,
        )
        self.labels[image_rel_path] = {
            "image_rel_path": image_rel_path,
            "export_path": row["export_path"],
            "text": normalize_text(text),
            "status": canonicalize_status(status),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "total_rotate_k": total_rotate_k,
            "total_flip_horizontal": total_flip_horizontal,
            "image_updated": image_updated,
        }
        self.write_outputs()

    def write_outputs(self) -> None:
        ordered_labels: List[Dict[str, object]] = []
        rec_lines: List[str] = []
        for row in self.rows:
            item = self.labels.get(row["image_rel_path"])
            if not item:
                continue
            item["status"] = canonicalize_status(str(item.get("status", "")))
            ordered_labels.append(item)
            if item["status"] == STATUS_OK:
                rec_lines.append(f"{row['export_path']}\t{item['text']}")

        write_labels_tsv(self.labels_tsv, ordered_labels)
        ensure_dir(self.output_file.parent)
        with self.output_file.open("w", encoding="utf-8") as f:
            for line in rec_lines:
                f.write(line + "\n")

    def counts(self) -> Dict[str, int]:
        ok = 0
        reject = 0
        skip = 0
        pending = 0
        for row in self.rows:
            bucket = self.row_bucket(row["image_rel_path"])
            if bucket == STATUS_OK:
                ok += 1
            elif bucket == "reject":
                reject += 1
            elif bucket == STATUS_SKIP:
                skip += 1
            else:
                pending += 1
        return {
            "total": len(self.rows),
            "labeled": ok + reject + skip,
            "ok": ok,
            "reject": reject,
            "skip": skip,
            "pending": pending,
        }


def render_sidebar(state: AppState, current_index: int) -> str:
    items: List[str] = []
    for idx, row in enumerate(state.rows):
        image_rel_path = row["image_rel_path"]
        bucket = state.row_bucket(image_rel_path)
        current_class = " current" if idx == current_index else ""
        items.append(
            f'<a class="queue-item{current_class}" href="/?{urlencode({"i": idx})}" '
            f'title="{html.escape(image_rel_path)}">'
            f'<span class="queue-mark {bucket}">{bucket_icon(bucket)}</span>'
            f'<span class="queue-index">{idx + 1:04d}</span>'
            f'<span class="queue-name">{html.escape(image_rel_path)}</span>'
            f"</a>"
        )
    return "".join(items)


def make_handler(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._handle_index(parsed)
                return
            if parsed.path == "/image":
                self._handle_image(parsed)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "未知路由")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/save":
                self.send_error(HTTPStatus.NOT_FOUND, "未知路由")
                return

            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(body)

            image_rel_path = form.get("image_rel_path", [""])[0]
            text = form.get("text", [""])[0]
            status = form.get("status", [STATUS_OK])[0]
            index = safe_index(form.get("index", ["0"])[0], len(state.rows))
            action = form.get("action", ["save_next"])[0]
            delta_rotate_k = parse_rotate_k(form.get("rotate_k", ["0"])[0])
            delta_flip_horizontal = parse_bool_flag(form.get("flip_horizontal", ["0"])[0])

            if action == "reject_next":
                text = REJECT_TEXT
                status = STATUS_OK

            state.save_label(
                image_rel_path=image_rel_path,
                text=text,
                status=status,
                delta_rotate_k=delta_rotate_k,
                delta_flip_horizontal=delta_flip_horizontal,
            )

            if action == "save_prev":
                next_index = max(0, index - 1)
            elif action == "save":
                next_index = index
            else:
                next_index = min(len(state.rows) - 1, index + 1)

            state.remember_current(state.rows[next_index]["image_rel_path"])
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", f"/?{urlencode({'i': next_index})}")
            self.end_headers()

        def _handle_index(self, parsed) -> None:
            query = parse_qs(parsed.query)
            if "i" in query:
                index = safe_index(query.get("i", ["0"])[0], len(state.rows))
            else:
                index = state.resume_index()

            row = state.rows[index]
            image_rel_path = row["image_rel_path"]
            state.remember_current(image_rel_path)
            label = state.get_label(image_rel_path)
            current_bucket = state.row_bucket(image_rel_path)
            counts = state.counts()
            sidebar = render_sidebar(state, index)
            prev_index = max(0, index - 1)
            next_index = min(len(state.rows) - 1, index + 1)
            saved_rotate_k, saved_flip_horizontal, image_updated = state.get_saved_transform(image_rel_path)
            saved_transform_text = describe_transform(saved_rotate_k, saved_flip_horizontal)

            page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>OCR 无框标注工具</title>
  <style>
    * {{ box-sizing: border-box; }}
    html {{ height: 100%; }}
    body {{ font-family: sans-serif; margin: 0; background: #efe8dd; color: #1e1a16; min-height: 100%; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 20px; align-items: start; max-width: 1580px; margin: 0 auto; padding: 20px; }}
    .card, .sidebar {{ background: #fffdf8; border: 1px solid #d8d0c2; border-radius: 14px; }}
    .card {{ padding: 20px; }}
    .sidebar {{ position: sticky; top: 20px; height: calc(100vh - 40px); padding: 14px; display: flex; flex-direction: column; overflow: hidden; }}
    .stats {{ font-weight: 600; margin-bottom: 8px; }}
    .meta {{ color: #5a5247; margin: 6px 0; word-break: break-all; }}
    .navrow, .toolbar, .legend, .transform-tools {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
    .navrow {{ margin: 14px 0; }}
    .transform-tools {{ margin: 14px 0 10px; }}
    .legend {{ margin: 10px 0 14px; color: #5a5247; font-size: 14px; }}
    img {{ max-width: 100%; max-height: 560px; display: block; margin: 18px auto; border: 1px solid #d9d1c3; background: #fff; }}
    input[type=text] {{ width: 100%; font-size: 30px; padding: 12px 14px; }}
    button, .navbtn, .queue-item {{ font-size: 16px; }}
    button, .navbtn {{ padding: 10px 14px; border: 1px solid #c8bda9; border-radius: 10px; background: #f7f1e7; color: #1e1a16; text-decoration: none; cursor: pointer; }}
    button.primary {{ background: #e6f2e1; border-color: #a0c28f; }}
    button.reject {{ background: #f6e6e3; border-color: #d6a9a0; }}
    button.secondary {{ background: #edf1f7; border-color: #aab8cf; }}
    .toolbar {{ margin-top: 16px; }}
    .hint {{ color: #5a5247; margin-top: 16px; line-height: 1.5; }}
    .status-chip {{ display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 999px; background: #f4eee4; color: #5a5247; font-size: 14px; }}
    .sidebar-title {{ font-weight: 700; margin-bottom: 10px; }}
    .queue-wrap {{ flex: 1 1 auto; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; padding-right: 4px; }}
    .queue-item {{ display: grid; grid-template-columns: 28px 54px minmax(0, 1fr); gap: 8px; align-items: center; padding: 8px 10px; border-radius: 10px; text-decoration: none; color: inherit; border: 1px solid #ece2d2; }}
    .queue-item.current {{ border-color: #9c7f51; background: #fbf4e8; }}
    .queue-mark {{ display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; font-weight: 700; }}
    .queue-mark.ok {{ color: #2f7d32; }}
    .queue-mark.reject {{ color: #b87800; }}
    .queue-mark.skip {{ color: #b53a2f; }}
    .queue-mark.pending {{ color: #8b7b68; }}
    .queue-index {{ color: #8b7b68; font-family: monospace; }}
    .queue-name {{ overflow-wrap: anywhere; font-size: 14px; }}
    .transform-status {{ color: #5a5247; font-size: 14px; }}
    @media (max-width: 1100px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; height: auto; }}
      .queue-wrap {{ max-height: 320px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <div class="card">
      <div class="stats">当前: {index + 1}/{counts['total']} | 已处理: {counts['labeled']} | 正常: {counts['ok']} | 拒识(~): {counts['reject']} | 旧跳过: {counts['skip']} | 待处理: {counts['pending']}</div>
      <div class="meta">图像: {html.escape(row['image_rel_path'])}</div>
      <div class="meta">导出路径: {html.escape(row['export_path'])}</div>
      <div class="meta">已保存图像矫正: {html.escape(saved_transform_text)} | 已写回文件: {"是" if image_updated else "否"}</div>
      <div class="status-chip"><span class="queue-mark {current_bucket}">{bucket_icon(current_bucket)}</span><span>当前状态: {bucket_label(current_bucket)}</span></div>
      <div class="navrow">
        <a class="navbtn" href="/?{urlencode({'i': prev_index})}">上一张</a>
        <a class="navbtn" href="/?{urlencode({'i': next_index})}">下一张</a>
      </div>
      <img id="preview-img" src="/image?{urlencode({'path': row['image_rel_path'], 'rotate_k': 0, 'flip_horizontal': 0})}" alt="标注图像预览"/>
      <div class="transform-tools">
        <button class="secondary" type="button" id="rotate-left-btn">左转 90 度 (A)</button>
        <button class="secondary" type="button" id="rotate-right-btn">右转 90 度 (D)</button>
        <button class="secondary" type="button" id="mirror-btn">水平镜像 (M)</button>
        <button class="secondary" type="button" id="reset-btn">重置预览 (R)</button>
        <span class="transform-status" id="transform-status">预览变换: 无</span>
      </div>
      <form method="post" action="/save">
        <input type="hidden" name="image_rel_path" value="{html.escape(row['image_rel_path'])}"/>
        <input type="hidden" name="index" value="{index}"/>
        <input type="hidden" id="status-input" name="status" value="{STATUS_OK}"/>
        <input type="hidden" id="rotate-k-input" name="rotate_k" value="0"/>
        <input type="hidden" id="flip-horizontal-input" name="flip_horizontal" value="0"/>
        <input type="text" id="text-input" name="text" value="{html.escape(str(label.get('text', '')))}" autofocus />
        <div class="toolbar">
          <button class="primary" id="save-btn" type="submit" name="action" value="save">保存</button>
          <button class="reject" id="reject-btn" type="submit" name="action" value="reject_next">跳过 =&gt; ~ (Ctrl+Q)</button>
          <button class="primary" id="save-next-btn" type="submit" name="action" value="save_next">保存并下一张 (Ctrl+E / 回车)</button>
          <button id="save-prev-btn" type="submit" name="action" value="save_prev">保存并上一张</button>
        </div>
      </form>
      <div class="legend">
        <span><span class="queue-mark ok">&#10003;</span> 已标注</span>
        <span><span class="queue-mark reject">~</span> 拒识 (~)</span>
        <span><span class="queue-mark skip">&#10007;</span> 旧跳过</span>
        <span><span class="queue-mark pending">&#9723;</span> 待处理</span>
      </div>
      <div class="hint">回车会触发“保存并下一张”。预览中的旋转和镜像，只有点击保存类按钮后才会真正写回当前 crop 文件。快捷键 A/D/M/R 在输入框未聚焦时生效，Ctrl+Q 表示“跳过 =&gt; ~”，Ctrl+E 表示“保存并下一张”。</div>
    </div>
    <aside class="sidebar">
      <div class="sidebar-title">队列</div>
      <div class="queue-wrap">{sidebar}</div>
    </aside>
  </div>
  <script>
    const previewImg = document.getElementById('preview-img');
    const transformStatus = document.getElementById('transform-status');
    const statusInput = document.getElementById('status-input');
    const rotateInput = document.getElementById('rotate-k-input');
    const flipInput = document.getElementById('flip-horizontal-input');
    const textInput = document.getElementById('text-input');
    const saveButton = document.getElementById('save-btn');
    const rejectButton = document.getElementById('reject-btn');
    const saveNextButton = document.getElementById('save-next-btn');
    const savePrevButton = document.getElementById('save-prev-btn');
    const rotateLeftButton = document.getElementById('rotate-left-btn');
    const rotateRightButton = document.getElementById('rotate-right-btn');
    const mirrorButton = document.getElementById('mirror-btn');
    const resetButton = document.getElementById('reset-btn');
    const imageRelPath = {json.dumps(row['image_rel_path'])};

    const isTypingTarget = (target) => {{
      if (!target) return false;
      const tag = (target.tagName || '').toLowerCase();
      return tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable;
    }};

    const setOk = () => {{
      statusInput.value = {json.dumps(STATUS_OK)};
    }};

    const setReject = () => {{
      statusInput.value = {json.dumps(STATUS_OK)};
      textInput.value = {json.dumps(REJECT_TEXT)};
    }};

    const refreshPreview = () => {{
      const params = new URLSearchParams();
      params.set('path', imageRelPath);
      params.set('rotate_k', rotateInput.value);
      params.set('flip_horizontal', flipInput.value);
      params.set('ts', String(Date.now()));
      previewImg.src = `/image?${{params.toString()}}`;

      const rotateK = ((parseInt(rotateInput.value || '0', 10) % 4) + 4) % 4;
      const flipHorizontal = flipInput.value === '1';
      if (rotateK === 0 && !flipHorizontal) {{
        transformStatus.textContent = '预览变换: 无';
        return;
      }}
      const parts = [];
      if (rotateK !== 0) parts.push(`顺时针旋转 ${{rotateK * 90}} 度`);
      if (flipHorizontal) parts.push('水平镜像');
      transformStatus.textContent = `预览变换: ${{parts.join(' + ')}}`;
    }};

    rotateLeftButton.addEventListener('click', () => {{
      rotateInput.value = String((parseInt(rotateInput.value || '0', 10) + 3) % 4);
      refreshPreview();
    }});
    rotateRightButton.addEventListener('click', () => {{
      rotateInput.value = String((parseInt(rotateInput.value || '0', 10) + 1) % 4);
      refreshPreview();
    }});
    mirrorButton.addEventListener('click', () => {{
      flipInput.value = flipInput.value === '1' ? '0' : '1';
      refreshPreview();
    }});
    resetButton.addEventListener('click', () => {{
      rotateInput.value = '0';
      flipInput.value = '0';
      refreshPreview();
    }});

    saveButton.addEventListener('click', setOk);
    saveNextButton.addEventListener('click', setOk);
    savePrevButton.addEventListener('click', setOk);
    rejectButton.addEventListener('click', setReject);

    textInput.addEventListener('keydown', (event) => {{
      if (event.key === 'Enter') {{
        event.preventDefault();
        setOk();
        saveNextButton.click();
      }}
    }});

    document.addEventListener('keydown', (event) => {{
      if (event.isComposing || event.metaKey || event.altKey) {{
        return;
      }}
      const key = event.key.toLowerCase();
      if (event.ctrlKey) {{
        if (key === 'q') {{
          event.preventDefault();
          setReject();
          rejectButton.click();
        }} else if (key === 'e') {{
          event.preventDefault();
          setOk();
          saveNextButton.click();
        }}
        return;
      }}
      if (isTypingTarget(document.activeElement)) {{
        return;
      }}
      if (key === 'a') {{
        event.preventDefault();
        rotateLeftButton.click();
      }} else if (key === 'd') {{
        event.preventDefault();
        rotateRightButton.click();
      }} else if (key === 'm') {{
        event.preventDefault();
        mirrorButton.click();
      }} else if (key === 'r') {{
        event.preventDefault();
        resetButton.click();
      }}
    }});

    refreshPreview();
  </script>
</body>
</html>"""
            body = page.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_image(self, parsed) -> None:
            query = parse_qs(parsed.query)
            image_rel_path = query.get("path", [""])[0]
            rotate_k = parse_rotate_k(query.get("rotate_k", ["0"])[0])
            flip_horizontal = parse_bool_flag(query.get("flip_horizontal", ["0"])[0])
            path = state.get_image_path(image_rel_path)
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, f"图像不存在: {path}")
                return

            try:
                with Image.open(path) as image:
                    preview = apply_image_transform(image, rotate_k, flip_horizontal)
                    buffer = io.BytesIO()
                    preview.save(buffer, format="PNG")
                    data = buffer.getvalue()
            except Exception as exc:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"图像渲染失败: {exc}")
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args) -> None:
            sys.stdout.write(
                "%s - - [%s] %s\n"
                % (self.address_string(), self.log_date_time_string(), format % args)
            )

    return Handler


def build_rows(image_dir: Path, path_root: Path) -> List[Dict[str, str]]:
    rows = scan_images(image_dir)
    built_rows: List[Dict[str, str]] = []
    for row in rows:
        abs_path = image_dir / row["image_rel_path"]
        built_rows.append(
            {
                "image_rel_path": row["image_rel_path"],
                "export_path": resolve_relative(abs_path, path_root),
            }
        )
    return built_rows


def main() -> None:
    args = parse_args()
    interactive_selection = not args.image_dir
    if interactive_selection:
        image_dir = choose_image_dir_via_dialog()
        if image_dir is None:
            print("未选择目录，程序已退出。")
            return
    else:
        image_dir = Path(args.image_dir).expanduser().resolve()
    if not image_dir.is_dir():
        raise NotADirectoryError(image_dir)

    default_output_dir = runtime_output_dir() if interactive_selection else image_dir.parent
    default_output_stem = sanitize_filename(image_dir.name)
    output_file = (
        Path(args.output_file).expanduser().resolve()
        if args.output_file
        else default_output_dir / f"{default_output_stem}.txt"
    )
    if args.output_file and not output_file.suffix:
        raise ValueError(
            f"--output-file 必须是文件路径，例如 train.txt 或 rec_gt.txt，当前收到: {output_file}"
        )

    labels_tsv = (
        Path(args.labels_tsv).expanduser().resolve()
        if args.labels_tsv
        else output_file.with_name(f"{output_file.stem}_labels.tsv")
    )
    session_file = output_file.with_name(f"{output_file.stem}_session.json")
    path_root = (
        Path(args.path_root).expanduser().resolve()
        if args.path_root
        else (infer_path_root(image_dir) if interactive_selection else image_dir)
    )

    rows = build_rows(image_dir=image_dir, path_root=path_root)
    state = AppState(
        image_dir=image_dir,
        path_root=path_root,
        rows=rows,
        output_file=output_file,
        labels_tsv=labels_tsv,
        session_file=session_file,
    )

    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"无框 OCR 标注器已启动: http://{args.host}:{args.port}")
    print(f"图像目录: {image_dir}")
    print(f"标签输出文件: {output_file}")
    print(f"状态 TSV: {labels_tsv}")
    print(f"会话文件: {session_file}")
    print(f"备份目录: {state.backup_dir}")
    print(f"相对路径根目录: {path_root}")
    try:
        webbrowser.open(f"http://{args.host}:{args.port}/")
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止服务。")


if __name__ == "__main__":
    main()
