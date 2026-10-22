"""坐标与长度工具。

推理结果中的坐标在“方向矫正后”的图像坐标系下（见 run_inference_pipeline._apply_correction_label：
先按 label % 4 旋转，label >= 4 时再水平翻转）。竞赛要求按影像原始方位提交，这里做逆变换。
坐标按连续坐标处理（像素 i 覆盖 [i, i+1)），bbox 为 [x1, y1, x2, y2]。
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Box = Tuple[float, float, float, float]


def original_size(corrected_w: int, corrected_h: int, label: int) -> Tuple[int, int]:
    if label % 4 in (1, 3):
        return corrected_h, corrected_w
    return corrected_w, corrected_h


def corrected_to_original_point(x: float, y: float, label: int, orig_w: float, orig_h: float) -> Tuple[float, float]:
    rot = label % 4
    rot_w = orig_h if rot in (1, 3) else orig_w
    if label >= 4:
        x = rot_w - x
    if rot == 1:  # 原图逆时针 90°：(xo, yo) -> (yo, W - xo)
        return orig_w - y, x
    if rot == 2:
        return orig_w - x, orig_h - y
    if rot == 3:  # 原图顺时针 90°：(xo, yo) -> (H - yo, xo)
        return y, orig_h - x
    return x, y


def box_to_original(box: Sequence[float], label: int, orig_w: float, orig_h: float) -> Box:
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    pts = [corrected_to_original_point(px, py, label, orig_w, orig_h)
           for px, py in ((x1, y1), (x2, y1), (x1, y2), (x2, y2))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def axis_span(box: Sequence[float], axis: str) -> Tuple[float, float]:
    """沿 axis（'x' 或 'y'）方向的区间。"""
    return (float(box[0]), float(box[2])) if axis == "x" else (float(box[1]), float(box[3]))


def cross_axis(axis: str) -> str:
    return "y" if axis == "x" else "x"


def overlaps(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return a[0] < b[1] and a[1] > b[0]


def union_box(boxes: Sequence[Sequence[float]]) -> Box:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def feret_diameter(polygon: Sequence[Sequence[float]]) -> float:
    """多边形最大两点距离（直线长度 / 长径）。"""
    pts = [(float(p[0]), float(p[1])) for p in polygon]
    if len(pts) > 200:
        step = math.ceil(len(pts) / 200)
        pts = pts[::step]
    best = 0.0
    for i in range(len(pts)):
        xi, yi = pts[i]
        for j in range(i + 1, len(pts)):
            d = math.hypot(xi - pts[j][0], yi - pts[j][1])
            if d > best:
                best = d
    return best


def defect_length_px(box: Sequence[float], polygon: Optional[List] = None, straight: bool = False) -> float:
    """缺陷长度（像素）。有分割多边形用最大直径；否则 straight=True（裂纹按直线长度）取 bbox 对角线，其余取长边。"""
    if polygon and len(polygon) >= 3:
        return feret_diameter(polygon)
    w = float(box[2]) - float(box[0])
    h = float(box[3]) - float(box[1])
    return math.hypot(w, h) if straight else max(w, h)


def defect_dimensions_px(box: Sequence[float], polygon: Optional[List] = None) -> Tuple[float, float, float]:
    """返回 (长边像素, 短边像素, 长宽比 aspect_ratio)。
    NB/T 47013.2-2015 3.6/3.7：长宽比 <= 3 为圆形缺陷，> 3 为条形缺陷。
    """
    w = max(0.0, float(box[2]) - float(box[0]))
    h = max(0.0, float(box[3]) - float(box[1]))
    major = max(w, h)
    minor = max(min(w, h), 1.0)
    if polygon and len(polygon) >= 3:
        feret = feret_diameter(polygon)
        major = max(major, feret)
    ar = major / minor
    return major, minor, ar
