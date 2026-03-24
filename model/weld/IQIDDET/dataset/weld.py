#!/usr/bin/env python3
"""
Prepare IQI dataset (LabelMe) for F-Clip training.

Workflow:
1) Crop IQI polygon by min-area-rect (possibly rotated) and map line annotations.
2) Optionally rotate ROI if the first line is too horizontal.
3) Generate F-Clip training maps (lcmap/lcoff/lleng/angle) with limited augmentations.

Usage:
  python dataset/weld.py \
    --label_dir /path/to/label \
    --img_dir /path/to/img \
    --out_dir /path/to/output \
    --val_ratio 0.1 \
    --seed 0 \
    --angle_thresh 50 \
    --heatmap_resolution 64 \
    --input_resolution_h 256 \
    --input_resolution_w 256 \
    --debug
"""

import argparse
import json
import math
import os
from pathlib import Path
import random

import cv2
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare IQI dataset for F-Clip.")
    parser.add_argument("--label_dir", required=True, help="LabelMe json directory.")
    parser.add_argument("--img_dir", required=True, help="Image directory.")
    parser.add_argument("--out_dir", required=True, help="Output directory.")
    parser.add_argument("--val_ratio", type=float, default=0.1, help="Validation split ratio.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for split.")
    parser.add_argument("--angle_thresh", type=float, default=50.0, help="Rotate if angle > threshold.")
    parser.add_argument("--heatmap_resolution", type=int, default=64, help="Heatmap width (1 x W).")
    parser.add_argument("--input_resolution_h", type=int, default=256, help="Input resolution height.")
    parser.add_argument("--input_resolution_w", type=int, default=256, help="Input resolution width.")
    parser.add_argument("--debug", action="store_true", help="Save debug visualizations.")
    return parser.parse_args()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def resolve_image_path(img_dir: Path, image_path: str, json_path: Path) -> Path:
    if image_path:
        basename = os.path.basename(image_path)
        cand = img_dir / basename
        if cand.exists():
            return cand
    # fallback: try same stem
    stem = json_path.stem
    for ext in [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]:
        cand = img_dir / f"{stem}{ext}"
        if cand.exists():
            return cand
    raise FileNotFoundError(f"No image found for {json_path}")


def order_points(pts: np.ndarray) -> np.ndarray:
    # pts: (4,2)
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # tl
    rect[2] = pts[np.argmax(s)]  # br
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # tr
    rect[3] = pts[np.argmax(diff)]  # bl
    return rect


def crop_rotated_rect(image: np.ndarray, poly: np.ndarray):
    rect = cv2.minAreaRect(poly.astype(np.float32))
    box = cv2.boxPoints(rect)
    box = order_points(box)

    w1 = np.linalg.norm(box[0] - box[1])
    w2 = np.linalg.norm(box[2] - box[3])
    h1 = np.linalg.norm(box[0] - box[3])
    h2 = np.linalg.norm(box[1] - box[2])
    width = int(round(max(w1, w2)))
    height = int(round(max(h1, h2)))
    if width < 2 or height < 2:
        return None, None

    dst = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(box, dst)
    warped = cv2.warpPerspective(image, M, (width, height))
    return warped, M


def point_in_polygon(pt, poly):
    return cv2.pointPolygonTest(poly.astype(np.float32), (float(pt[0]), float(pt[1])), False) >= 0


def map_lines_perspective(lines_xy, M):
    if len(lines_xy) == 0:
        return np.zeros((0, 2, 2), dtype=np.float32)
    pts = np.array(lines_xy, dtype=np.float32).reshape(-1, 1, 2)
    pts_w = cv2.perspectiveTransform(pts, M).reshape(-1, 2)
    return pts_w.reshape(-1, 2, 2).astype(np.float32)


def angle_from_vertical(line_xy):
    (x1, y1), (x2, y2) = line_xy
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx < 1e-6 and dy < 1e-6:
        return 0.0
    return math.degrees(math.atan2(dx, dy))  # 0=vertical, 90=horizontal


def rotate_cw90(image, lines_xy):
    h, w = image.shape[:2]
    rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if len(lines_xy) == 0:
        return rotated, lines_xy
    new_lines = []
    for (x1, y1), (x2, y2) in lines_xy:
        nx1, ny1 = (h - 1 - y1), x1
        nx2, ny2 = (h - 1 - y2), x2
        new_lines.append([[nx1, ny1], [nx2, ny2]])
    return rotated, np.array(new_lines, dtype=np.float32)


def draw_lines(image, lines_xy, color=(0, 0, 255)):
    if image.ndim == 2:
        out = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        out = image.copy()
    for (x1, y1), (x2, y2) in lines_xy:
        p1 = (int(round(x1)), int(round(y1)))
        p2 = (int(round(x2)), int(round(y2)))
        cv2.line(out, p1, p2, color, 2, lineType=cv2.LINE_AA)
    return out


def apply_window_level(image: np.ndarray, window_width: int, window_level: int) -> np.ndarray:
    window_min = window_level - window_width / 2
    window_max = window_level + window_width / 2
    if window_max <= window_min:
        window_max = window_min + 1
    output = np.clip((image - window_min) / window_width * 255.0, 0, 255).astype(np.uint8)
    return output


def auto_window_level(image: np.ndarray):
    percentiles = np.percentile(image, [2, 98])
    img_min, img_max = percentiles[0], percentiles[1]
    img_mean = np.mean(image)
    img_std = np.std(image)
    window_level = int(img_mean)
    window_width = int(min(4 * img_std, img_max - img_min))
    window_width = max(1, window_width)
    return window_width, window_level


def apply_clahe(image: np.ndarray, clip_limit: float = 2.0, tile_grid_size=(8, 8)):
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(image)


def enhance_windowing_gray(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    img_float = gray.astype(np.float32, copy=False)
    ww, wl = auto_window_level(img_float)
    enhanced = apply_window_level(img_float, ww, wl)
    enhanced = apply_clahe(enhanced)
    return enhanced


def save_heatmap(prefix, image, lines, im_rescale, heatmap_w):
    heatmap_scale = (1, heatmap_w)

    lcmap = np.zeros(heatmap_scale, dtype=np.float32)
    lcoff = np.zeros((1,) + heatmap_scale, dtype=np.float32)
    lleng = np.zeros(heatmap_scale, dtype=np.float32)
    angle = np.zeros(heatmap_scale, dtype=np.float32)

    if lines is None or len(lines) == 0:
        lpos = np.zeros((0, 2, 2), dtype=np.float32)
        count = 0
        image = cv2.resize(image, im_rescale)
        np.savez_compressed(
            f"{prefix}_line.npz",
            lcmap=lcmap,
            lcoff=lcoff,
            lleng=lleng,
            angle=angle,
            lpos=lpos,
            count=count,
        )
        cv2.imwrite(f"{prefix}.png", image)
        return

    lines = np.array(lines, dtype=np.float32)

    fy_img = im_rescale[1] / image.shape[0]
    fx_img = im_rescale[0] / image.shape[1]
    lines_img = lines.copy()
    lines_img[:, :, 0] *= fx_img
    lines_img[:, :, 1] *= fy_img

    scale_heat = heatmap_w / im_rescale[0]
    lines_heat = lines_img * scale_heat
    lines_heat[:, :, 0] = np.clip(lines_heat[:, :, 0], 0, heatmap_w - 1e-4)
    lines_heat[:, :, 1] = np.clip(lines_heat[:, :, 1], 0, heatmap_w - 1e-4)
    lines_rc = lines_heat[:, :, ::-1]  # (r, c)
    lpos_all = lines_rc.astype(np.float32, copy=True)

    best = {}
    for idx, (v0, v1) in enumerate(lines_rc):
        v = (v0 + v1) / 2
        c = v[1]
        col = int(c)
        if col < 0 or col >= heatmap_w:
            continue
        x_off = c - col - 0.5
        abs_off = abs(x_off)
        prev = best.get(col)
        if prev is not None and abs_off >= prev["abs_off"]:
            continue

        lcmap[0, col] = 1
        lcoff[0, 0, col] = x_off
        lleng[0, col] = np.sqrt(np.sum((v0 - v1) ** 2)) / 2

        vv = v0 if v0[0] <= v[0] else v1
        if np.sqrt(np.sum((vv - v) ** 2)) > 1e-4:
            angle[0, col] = np.sum((vv - v) * np.array([0.0, 1.0])) / np.sqrt(np.sum((vv - v) ** 2))
        else:
            angle[0, col] = 0.0

        best[col] = {"abs_off": abs_off, "idx": idx}

    len_scale = heatmap_w / 2
    lleng = np.clip(lleng, 0, len_scale - 1e-4) / len_scale
    angle = lcmap * np.clip(angle, -1 + 1e-4, 1 - 1e-4)

    if best:
        keep_idx = [best[col]["idx"] for col in sorted(best.keys())]
        lpos = lpos_all[keep_idx]
    else:
        lpos = np.zeros((0, 2, 2), dtype=np.float32)
    count = int(lcmap.sum())

    image = cv2.resize(image, im_rescale)
    np.savez_compressed(
        f"{prefix}_line.npz",
        lcmap=lcmap,
        lcoff=lcoff,
        lleng=lleng,
        angle=angle,
        lpos=lpos,
        count=count,
    )
    cv2.imwrite(f"{prefix}.png", image)


def augment_and_save(base_prefix, image, lines, out_split, im_rescale, heatmap_w):
    # original
    save_heatmap(f"{out_split}/{base_prefix}_0", image, lines, im_rescale, heatmap_w)

    if lines is None:
        lines = np.zeros((0, 2, 2), dtype=np.float32)

    h, w = image.shape[:2]

    # hflip
    lines1 = lines.copy()
    if len(lines1) > 0:
        lines1[:, :, 0] = w - lines1[:, :, 0]
    im1 = image[:, ::-1]
    save_heatmap(f"{out_split}/{base_prefix}_1", im1, lines1, im_rescale, heatmap_w)

    # vflip
    lines2 = lines.copy()
    if len(lines2) > 0:
        lines2[:, :, 1] = h - lines2[:, :, 1]
    im2 = image[::-1, :]
    save_heatmap(f"{out_split}/{base_prefix}_2", im2, lines2, im_rescale, heatmap_w)

    # hv flip
    lines3 = lines.copy()
    if len(lines3) > 0:
        lines3[:, :, 0] = w - lines3[:, :, 0]
        lines3[:, :, 1] = h - lines3[:, :, 1]
    im3 = image[::-1, ::-1]
    save_heatmap(f"{out_split}/{base_prefix}_3", im3, lines3, im_rescale, heatmap_w)


def main():
    args = parse_args()
    label_dir = Path(args.label_dir)
    img_dir = Path(args.img_dir)
    out_dir = Path(args.out_dir)

    train_dir = out_dir / "train"
    valid_dir = out_dir / "valid"
    debug_ori = out_dir / "debug" / "ori"
    debug_rot = out_dir / "debug" / "rotate"
    debug_enh = out_dir / "debug" / "enhance"

    ensure_dir(train_dir)
    ensure_dir(valid_dir)
    if args.debug:
        ensure_dir(debug_ori)
        ensure_dir(debug_rot)
        ensure_dir(debug_enh)

    json_files = sorted(label_dir.glob("*.json"))
    samples = []
    processed_polys = 0
    train_samples = 0
    valid_samples = 0

    im_rescale = (args.input_resolution_w, args.input_resolution_h)
    heatmap_w = args.heatmap_resolution

    for jp in json_files:
        with open(jp, "r", encoding="utf-8") as f:
            data = json.load(f)
        polys = [s for s in data.get("shapes", []) if s.get("shape_type") == "polygon"]
        for pidx, _ in enumerate(polys):
            samples.append((jp, pidx))

    random.seed(args.seed)
    random.shuffle(samples)
    total_polys = len(samples)
    val_count = int(len(samples) * args.val_ratio)
    val_set = set(samples[:val_count])

    for jp in json_files:
        with open(jp, "r", encoding="utf-8") as f:
            data = json.load(f)

        image_path = resolve_image_path(img_dir, data.get("imagePath"), jp)
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"Skip (image read fail): {image_path}")
            continue

        shapes = data.get("shapes", [])
        polys = [s for s in shapes if s.get("shape_type") == "polygon"]
        lines = [s for s in shapes if s.get("shape_type") == "line"]

        # keep original order for lines
        line_pts = []
        for s in lines:
            pts = s.get("points", [])
            if len(pts) >= 2:
                line_pts.append([pts[0], pts[1]])

        for pidx, poly_s in enumerate(polys):
            sample_key = (jp, pidx)
            split_dir = valid_dir if sample_key in val_set else train_dir
            base_id = f"{image_path.stem}_p{pidx}"

            poly = np.array(poly_s.get("points", []), dtype=np.float32)
            if len(poly) < 3:
                continue

            # select lines fully inside polygon
            inside_lines = []
            for ln in line_pts:
                p1, p2 = ln
                if point_in_polygon(p1, poly) and point_in_polygon(p2, poly):
                    inside_lines.append(ln)

            roi, M = crop_rotated_rect(image, poly)
            if roi is None:
                continue

            mapped_lines = map_lines_perspective(inside_lines, M)

            if args.debug:
                dbg = draw_lines(roi, mapped_lines)
                cv2.imwrite(str(debug_ori / f"{base_id}.png"), dbg)

            # rotate if needed (based on first line)
            if len(mapped_lines) > 0:
                ang = angle_from_vertical(mapped_lines[0])
                if ang > args.angle_thresh:
                    roi, mapped_lines = rotate_cw90(roi, mapped_lines)
                    if args.debug:
                        dbg = draw_lines(roi, mapped_lines)
                        cv2.imwrite(str(debug_rot / f"{base_id}.png"), dbg)
                elif args.debug:
                    dbg = draw_lines(roi, mapped_lines)
                    cv2.imwrite(str(debug_rot / f"{base_id}.png"), dbg)
            elif args.debug:
                cv2.imwrite(str(debug_rot / f"{base_id}.png"), roi)

            roi = enhance_windowing_gray(roi)
            if args.debug:
                dbg = draw_lines(roi, mapped_lines)
                cv2.imwrite(str(debug_enh / f"{base_id}.png"), dbg)

            augment_and_save(base_id, roi, mapped_lines, str(split_dir), im_rescale, heatmap_w)
            processed_polys += 1
            if split_dir == train_dir:
                train_samples += 4
            else:
                valid_samples += 4

            if processed_polys % 50 == 0 or processed_polys == total_polys:
                print(
                    f"Processed {processed_polys}/{total_polys} polygons "
                    f"(train samples: {train_samples}, valid samples: {valid_samples})"
                )

    print(
        f"Done. polygons: {processed_polys}, "
        f"train samples: {train_samples}, valid samples: {valid_samples}"
    )


if __name__ == "__main__":
    main()
