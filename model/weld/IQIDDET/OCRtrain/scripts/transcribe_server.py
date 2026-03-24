#!/usr/bin/env python3
"""Tiny web UI for manually transcribing text-detection crops."""

from __future__ import annotations

import argparse
import html
import io
import os
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, quote, urlencode, urlparse

from common import get_default_dataset_root, load_label_tsv, read_jsonl, write_label_tsv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal crop transcription web UI.")
    parser.add_argument(
        "--dataset-root",
        default=str(get_default_dataset_root()),
        help="Dataset root created under local/OCRdatasets.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Crop manifest JSONL. Defaults to manifests/crops_train.jsonl.",
    )
    parser.add_argument(
        "--labels-tsv",
        default=None,
        help="Output TSV for manual transcripts. Defaults to annotations/<manifest_stem>_labels.tsv.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    return parser.parse_args()


def build_rows(manifest_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for row in read_jsonl(manifest_path):
        if row.get("status") != "ok":
            continue
        rows.append(row)
    if not rows:
        raise RuntimeError(f"No valid crop rows found in {manifest_path}")
    return rows


class AppState:
    def __init__(self, dataset_root: Path, rows: List[Dict[str, str]], labels_path: Path):
        self.dataset_root = dataset_root
        self.rows = rows
        self.labels_path = labels_path
        self.labels = load_label_tsv(labels_path)

    def save_label(self, sample_id: str, text: str, status: str, crop_rel_path: str) -> None:
        self.labels[sample_id] = {
            "sample_id": sample_id,
            "text": text,
            "status": status,
            "crop_rel_path": crop_rel_path,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        ordered = []
        for row in self.rows:
            item = self.labels.get(row["sample_id"])
            if not item:
                continue
            ordered.append(item)
        write_label_tsv(self.labels_path, ordered)


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
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/save":
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(body)

            sample_id = form.get("sample_id", [""])[0]
            text = form.get("text", [""])[0]
            status = form.get("status", ["ok"])[0]
            crop_rel_path = form.get("crop_rel_path", [""])[0]
            index = int(form.get("index", ["0"])[0])
            action = form.get("action", ["next"])[0]

            state.save_label(sample_id, text, status, crop_rel_path)

            if action == "prev":
                index = max(0, index - 1)
            elif action == "stay":
                index = index
            else:
                index = min(len(state.rows) - 1, index + 1)

            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", f"/?{urlencode({'i': index})}")
            self.end_headers()

        def _handle_index(self, parsed) -> None:
            query = parse_qs(parsed.query)
            index = int(query.get("i", ["0"])[0])
            index = max(0, min(index, len(state.rows) - 1))
            row = state.rows[index]
            label = state.labels.get(row["sample_id"], {})
            labeled = sum(1 for item in state.rows if item["sample_id"] in state.labels)

            page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>OCR Crop Transcriber</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; background: #f3f0ea; color: #1f1c18; }}
    .wrap {{ max-width: 960px; margin: 0 auto; }}
    .card {{ background: #fffdf8; border: 1px solid #d8d0c2; border-radius: 14px; padding: 20px; }}
    img {{ max-width: 100%; max-height: 280px; border: 1px solid #d9d1c3; background: #fff; }}
    input[type=text] {{ width: 100%; font-size: 28px; padding: 10px 12px; margin-top: 12px; }}
    select, button {{ font-size: 16px; padding: 8px 12px; margin-right: 8px; }}
    .meta {{ margin: 10px 0 16px; color: #5a5247; }}
    .toolbar {{ margin-top: 16px; }}
    .progress {{ font-weight: 600; margin-bottom: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="progress">Progress: {labeled}/{len(state.rows)} | Current: {index + 1}/{len(state.rows)}</div>
      <div class="meta">sample_id: {html.escape(row['sample_id'])}</div>
      <div class="meta">crop: {html.escape(row['crop_relative_path'])}</div>
      <img src="/image?sample_id={quote(row['sample_id'])}" alt="crop"/>
      <form method="post" action="/save">
        <input type="hidden" name="sample_id" value="{html.escape(row['sample_id'])}"/>
        <input type="hidden" name="crop_rel_path" value="{html.escape(row['crop_relative_path'])}"/>
        <input type="hidden" name="index" value="{index}"/>
        <input type="text" name="text" value="{html.escape(label.get('text', ''))}" autofocus />
        <div class="toolbar">
          <select name="status">
            {render_status_options(label.get('status', 'ok'))}
          </select>
          <button type="submit" name="action" value="next">Save + Next</button>
          <button type="submit" name="action" value="prev">Save + Prev</button>
          <button type="submit" name="action" value="stay">Save</button>
        </div>
      </form>
      <p class="meta">Keyboard hint: type transcript, press Enter for Save + Next.</p>
    </div>
  </div>
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
            sample_id = query.get("sample_id", [""])[0]
            row = next((item for item in state.rows if item["sample_id"] == sample_id), None)
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Sample not found")
                return
            path = state.dataset_root / row["crop_relative_path"]
            if not path.exists():
                self.send_error(HTTPStatus.NOT_FOUND, f"Image not found: {path}")
                return
            data = path.read_bytes()
            content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args) -> None:
            sys.stdout.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    return Handler


def render_status_options(current: str) -> str:
    options = []
    for value in ["ok", "skip", "unclear"]:
        selected = " selected" if value == current else ""
        options.append(f'<option value="{value}"{selected}>{value}</option>')
    return "".join(options)


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root).resolve()
    manifest_path = Path(args.manifest).resolve() if args.manifest else dataset_root / "manifests" / "crops_train.jsonl"
    labels_path = Path(args.labels_tsv).resolve() if args.labels_tsv else dataset_root / "annotations" / f"{manifest_path.stem}_labels.tsv"
    rows = build_rows(manifest_path)
    state = AppState(dataset_root=dataset_root, rows=rows, labels_path=labels_path)

    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"Serving transcription UI on http://{args.host}:{args.port}")
    print(f"Manifest: {manifest_path}")
    print(f"Labels TSV: {labels_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


if __name__ == "__main__":
    main()
