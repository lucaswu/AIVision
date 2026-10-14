"""在（方向矫正后的）原图上叠加检测结果，生成标注图。

结果 JSON 里的坐标都在"方向矫正后"的图像坐标系下，所以这里要先按
correction.label 对原图做同样的旋转/翻转，再画框。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from utils import cv_io
from utils.pipeline_utils import FontRenderer, load_image

Color = Tuple[int, int, int]

_PALETTE: Tuple[Color, ...] = (
    (0, 0, 255), (0, 165, 255), (0, 215, 255), (0, 200, 0),
    (255, 144, 30), (255, 0, 255), (180, 105, 255), (200, 200, 0),
)


_FONT_CACHE: Dict[int, FontRenderer] = {}


def _font_for(image_shape) -> FontRenderer:
    size = max(16, int(round(max(image_shape[:2]) / 60)))
    size = (size // 4) * 4  # 量化，便于复用缓存
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = FontRenderer(font_size=size)
    return _FONT_CACHE[size]


def class_color(name: str) -> Color:
    digest = hashlib.md5(name.encode("utf-8")).digest()
    return _PALETTE[digest[0] % len(_PALETTE)]


def apply_correction_label(image: np.ndarray, label_idx: int) -> np.ndarray:
    """与 run_inference_pipeline._apply_correction_label 等价（保持无重依赖）。"""
    img = image
    rot_state = label_idx % 4
    if rot_state == 1:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rot_state == 2:
        img = cv2.rotate(img, cv2.ROTATE_180)
    elif rot_state == 3:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if label_idx >= 4:
        img = cv2.flip(img, 1)
    return img


def _source_path(result: Dict[str, Any]) -> Path:
    # 16bit/DICOM 会先转成 8bit 的 prepared 图，推理实际用的是它
    return Path(result.get("preprocessed_path") or result["image_path"])


def draw_result(image: np.ndarray, result: Dict[str, Any], font: Optional[FontRenderer] = None) -> np.ndarray:
    """在已矫正的 BGR 图上叠加缺陷框/多边形、焊缝位置、缺陷位置原点、IQI 摘要。"""
    canvas = np.ascontiguousarray(image.copy())
    h, w = canvas.shape[:2]
    thick = max(2, int(round(max(h, w) / 1000)))
    font = font or _font_for(canvas.shape)

    for roi in result.get("rois") or []:
        bx = roi.get("bbox")
        if bx and len(bx) == 4:
            cv2.rectangle(canvas, (int(bx[0]), int(bx[1])), (int(bx[2]), int(bx[3])), (160, 160, 160), 1)
        for d in (roi.get("defects") or roi.get("detections") or []):
            name = str(d.get("class_name", d.get("class_id", "?")))
            color = class_color(name)
            poly = d.get("polygon")
            if poly and len(poly) >= 3:
                pts = np.array(poly, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(canvas, [pts], True, color, thick, cv2.LINE_AA)
            box = d.get("bbox")
            if box and len(box) == 4:
                x1, y1, x2, y2 = (int(v) for v in box)
                cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thick)
                conf = d.get("confidence")
                label = f"{name} {conf:.2f}" if isinstance(conf, (int, float)) else name
                font.draw(canvas, label, (x1, max(0, y1 - font.font_size - 2)), color)

    for loc in result.get("weld_location") or []:
        kps = loc.get("keypoints") or []
        for kp in kps:
            cv2.circle(canvas, (int(kp["x"]), int(kp["y"])), thick * 3, (0, 255, 255), -1)
        box = loc.get("bbox")
        if box and len(box) == 4:
            cv2.rectangle(canvas, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 255), thick)

    dp = result.get("defect_position") or {}
    if dp.get("detected") and dp.get("origin_x") is not None and dp.get("origin_y") is not None:
        ox, oy = int(dp["origin_x"]), int(dp["origin_y"])
        cv2.drawMarker(canvas, (ox, oy), (0, 0, 255), cv2.MARKER_CROSS, 50, thick + 1)
        cv2.circle(canvas, (ox, oy), 30, (0, 255, 0), thick)

    ocr = result.get("ocr") or {}
    summary = []
    if ocr.get("plate_code") is not None:
        summary.append(f"IQI: {ocr.get('plate_code')}")
    if ocr.get("grade") is not None:
        summary.append(f"grade: {ocr.get('grade')}")
    if result.get("grayscale_density") is not None:
        summary.append(f"density: {result.get('grayscale_density')}")
    if summary:
        font.draw(canvas, "  ".join(summary), (10, 10), (0, 255, 0))
    return canvas


def render_annotated(result: Dict[str, Any], font: Optional[FontRenderer] = None) -> np.ndarray:
    """读取推理所用图像 → 矫正方向 → 叠加结果。"""
    image = load_image(_source_path(result))
    label = int((result.get("correction") or {}).get("label", 0) or 0)
    if label:
        image = apply_correction_label(image, label)
    return draw_result(image, result, font)


def save_annotated(result: Dict[str, Any], out_path: Path, font: Optional[FontRenderer] = None,
                   quality: int = 92) -> Path:
    canvas = render_annotated(result, font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    params = [int(cv2.IMWRITE_JPEG_QUALITY), quality] if out_path.suffix.lower() in (".jpg", ".jpeg") else None
    if not cv_io.imwrite(out_path, canvas, params):
        raise RuntimeError(f"写入标注图失败: {out_path}")
    return out_path
