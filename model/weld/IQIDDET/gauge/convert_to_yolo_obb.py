#!/usr/bin/env python3
"""Convert LabelMe polygons to YOLO-OBB format.

YOLO OBB label format:
  class_index x1 y1 x2 y2 x3 y3 x4 y4
Coordinates are normalized to [0, 1].
"""

import argparse
import json
import os
import random
import shutil
from pathlib import Path

import cv2
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Convert LabelMe polygons to YOLO-OBB format.")
    parser.add_argument("--label_dir", required=True, help="LabelMe json directory.")
    parser.add_argument("--img_dir", required=True, help="Image directory.")
    parser.add_argument("--out_dir", required=True, help="Output directory for YOLO-OBB dataset.")
    parser.add_argument("--val_ratio", type=float, default=0.1, help="Validation split ratio.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for split.")
    parser.add_argument("--class_name", default="IQI", help="Class name for all polygons.")
    parser.add_argument("--label_filter", default="", help="Only keep polygons with this label name.")
    return parser.parse_args()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def resolve_image_path(img_dir: Path, image_path: str, json_path: Path) -> Path:
    if image_path:
        basename = os.path.basename(image_path)
        cand = img_dir / basename
        if cand.exists():
            return cand
    stem = json_path.stem
    for ext in [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]:
        cand = img_dir / f"{stem}{ext}"
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No image found for {json_path}")


def order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def polygon_to_obb(poly: np.ndarray):
    rect = cv2.minAreaRect(poly.astype(np.float32))
    box = cv2.boxPoints(rect)
    box = order_points(box)
    return box.astype(np.float32)


def write_data_yaml(out_dir: Path, class_name: str):
    data_yaml = out_dir / "data.yaml"
    with open(data_yaml, "w", encoding="utf-8") as f:
        f.write(f"path: {out_dir.as_posix()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("names:\n")
        f.write(f"  0: {class_name}\n")


def main():
    args = parse_args()
    label_dir = Path(args.label_dir)
    img_dir = Path(args.img_dir)
    out_dir = Path(args.out_dir)

    images_train = out_dir / "images" / "train"
    images_val = out_dir / "images" / "val"
    labels_train = out_dir / "labels" / "train"
    labels_val = out_dir / "labels" / "val"
    for p in [images_train, images_val, labels_train, labels_val]:
        ensure_dir(p)

    json_files = sorted(label_dir.glob("*.json"))
    random.seed(args.seed)
    random.shuffle(json_files)
    val_count = int(len(json_files) * args.val_ratio)
    val_set = set(json_files[:val_count])

    processed = 0
    for jp in json_files:
        with open(jp, "r", encoding="utf-8") as f:
            data = json.load(f)

        image_path = resolve_image_path(img_dir, data.get("imagePath"), jp)
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"Skip (image read fail): {image_path}")
            continue

        h, w = image.shape[:2]
        shapes = data.get("shapes", [])
        polys = [s for s in shapes if s.get("shape_type") == "polygon"]

        split_dir = "val" if jp in val_set else "train"
        label_dir_out = labels_val if split_dir == "val" else labels_train
        img_dir_out = images_val if split_dir == "val" else images_train

        label_lines = []
        for s in polys:
            if args.label_filter and s.get("label") != args.label_filter:
                continue
            pts = np.array(s.get("points", []), dtype=np.float32)
            if len(pts) < 3:
                continue
            obb = polygon_to_obb(pts)
            if obb.shape != (4, 2):
                continue
            obb[:, 0] = np.clip(obb[:, 0] / float(w), 0.0, 1.0)
            obb[:, 1] = np.clip(obb[:, 1] / float(h), 0.0, 1.0)
            coords = " ".join(f"{v:.6f}" for v in obb.reshape(-1))
            label_lines.append(f"0 {coords}")

        out_img = img_dir_out / image_path.name
        if not out_img.exists():
            shutil.copy2(image_path, out_img)

        label_path = label_dir_out / f"{image_path.stem}.txt"
        with open(label_path, "w", encoding="utf-8") as f:
            if label_lines:
                f.write("\n".join(label_lines) + "\n")
            else:
                f.write("")

        processed += 1
        if processed % 50 == 0 or processed == len(json_files):
            print(f"Processed {processed}/{len(json_files)} images")

    write_data_yaml(out_dir, args.class_name)
    print(f"Done. images: {processed}")


if __name__ == "__main__":
    main()
