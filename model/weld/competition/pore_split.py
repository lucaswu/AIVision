"""圆形缺陷框内精细拆分：把“一群气孔被框成一个大框”拆回逐个气孔，并按真实轮廓量长径。

检测模型常把密集小气孔框成一个大框，按框尺寸当作单个气孔会把点数算成 25、甚至因“长径 > T/2”
直接判 Ⅳ 级。这里在框内（原始高位灰度图，与检测坐标系一致）：
1. 中值抛光（median polish：行中值 + 列中值）估计局部背景并扣除。焊缝区域本身有明暗渐变，
   不能全局阈值；焊缝灰度主要随“垂直焊缝方向”变化、沿焊缝缓变，正好是行/列可分的背景。
   裁剪区在框外各扩一个框长，保证每行/列中气孔占比 < 1/2，中值不受气孔影响。
   （大尺度高斯模糊在焊缝亮/暗带弯曲处有 ~σ²·曲率 的偏差，大结构元形态学会被亮带抬高，均不可靠）；
2. 气孔极性默认“暗”：气孔处金属少、底片黑度大，在本系统的显示约定下（焊缝亮；MONOCHROME1 已反相）
   呈暗点。真实底片验证：焊缝起弧/收弧处的亮斑会让“自动极性”误选亮侧，因此不默认自动；
3. 按 k·σ（σ 为残差的稳健噪声估计）阈值 + 开运算去噪，8 连通分量即单个气孔；
   每个气孔的外接框按“该气孔峰值残差的一半”重新取边（半高宽），尺寸不随对比度/低阈值偏大；
4. 逐个复核（真实底片上背景模型在亮斑边缘、焊缝纹理处会产生伪分量）：形状紧凑（填充率、长宽比 ≤ 3，
   即标准对圆形缺陷的定义）且比紧邻的一圈背景暗/亮出 k·σ（局部对比，不依赖背景模型）。
没有可信分量时返回 None，调用方保留原框。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

Box = Tuple[float, float, float, float]


@dataclass
class SplitConfig:
    k_sigma: float = 4.0          # 残差 > k·σ 视为气孔像素
    min_area_px: int = 6          # 小于该面积的分量视为噪声（0.042mm/px 时约 0.1mm 直径）
    pad_ratio: float = 1.0        # 背景估计时框外扩比例（各方向扩 pad_ratio × 框长边）
    min_pad_px: int = 12
    polarity: str = "dark"        # dark | bright | auto（auto：框内哪侧残差尾部更突出取哪侧）
    min_fill: float = 0.45        # 分量面积 / 外接框面积
    max_aspect: float = 3.0       # 长宽比 > 3 不是圆形缺陷
    ring_px: int = 4              # 局部对比的背景环宽度


def _robust_sigma(values: np.ndarray) -> float:
    med = float(np.median(values))
    return 1.4826 * float(np.median(np.abs(values - med))) or 1e-6


def split_pores(image: np.ndarray, box: Sequence[float], cfg: Optional[SplitConfig] = None) -> Optional[List[Box]]:
    """返回框内各气孔的外接框（图像坐标，[x1, y1, x2, y2)）；无法可靠拆分时返回 None。"""
    import cv2

    cfg = cfg or SplitConfig()
    h, w = image.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    bw, bh = x2 - x1, y2 - y1
    if bw < 2 or bh < 2:
        return None
    pad = max(cfg.min_pad_px, int(cfg.pad_ratio * max(bw, bh)))
    cx1, cy1 = max(0, int(x1) - pad), max(0, int(y1) - pad)
    cx2, cy2 = min(w, int(np.ceil(x2)) + pad), min(h, int(np.ceil(y2)) + pad)
    crop = image[cy1:cy2, cx1:cx2].astype(np.float32)
    if crop.ndim == 3:
        crop = crop.mean(axis=2)
    if crop.size == 0:
        return None

    # 轻度平滑压噪
    crop = cv2.GaussianBlur(crop, (0, 0), 1.0)
    background = np.zeros_like(crop)
    for _ in range(2):
        background += np.median(crop - background, axis=1, keepdims=True)
        background += np.median(crop - background, axis=0, keepdims=True)
    residual = crop - background

    bx1, by1 = int(x1) - cx1, int(y1) - cy1
    bx2, by2 = int(np.ceil(x2)) - cx1, int(np.ceil(y2)) - cy1
    if bx2 <= bx1 or by2 <= by1:
        return None
    inside = residual[by1:by2, bx1:bx2]
    sign = 1.0
    if cfg.polarity == "dark" or (cfg.polarity == "auto" and abs(float(np.percentile(inside, 0.5)))
                                  > abs(float(np.percentile(inside, 99.5)))):
        residual, sign = -residual, -1.0
    signed = sign * crop  # 气孔为正向
    noise = _robust_sigma(residual)
    mask = (residual > cfg.k_sigma * noise).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes: List[Box] = []
    for i in range(1, n):
        sx, sy, sw, sh, area = (int(v) for v in stats[i])
        cx, cy = centroids[i]
        if area < cfg.min_area_px or not (bx1 <= cx < bx2 and by1 <= cy < by2):
            continue
        if area < cfg.min_fill * sw * sh or max(sw, sh) > cfg.max_aspect * min(sw, sh):
            continue
        # 局部对比：分量均值 vs 外扩一圈（隔 2px）的中值
        m = cfg.ring_px + 2
        ry1, rx1 = max(0, sy - m), max(0, sx - m)
        ry2, rx2 = min(mask.shape[0], sy + sh + m), min(mask.shape[1], sx + sw + m)
        comp_full = (labels[ry1:ry2, rx1:rx2] == i).astype(np.uint8)
        near = cv2.dilate(comp_full, np.ones((5, 5), np.uint8))
        ring = cv2.dilate(comp_full, np.ones((2 * m + 1, 2 * m + 1), np.uint8)).astype(bool) & ~near.astype(bool)
        region = signed[ry1:ry2, rx1:rx2]
        if not ring.any() or float(region[comp_full.astype(bool)].mean()) - float(np.median(region[ring])) \
                < cfg.k_sigma * noise:
            continue
        comp = labels[sy:sy + sh, sx:sx + sw] == i
        res = residual[sy:sy + sh, sx:sx + sw]
        half = comp & (res >= 0.5 * float(np.percentile(res[comp], 90)))  # 峰值取 90 分位，抗噪声
        ys, xs = np.nonzero(half)
        boxes.append((float(cx1 + sx + xs.min()), float(cy1 + sy + ys.min()),
                      float(cx1 + sx + xs.max() + 1), float(cy1 + sy + ys.max() + 1)))
    return boxes or None
