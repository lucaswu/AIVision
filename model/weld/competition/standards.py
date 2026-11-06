"""NB/T 47013.2-2015 质量分级用到的表格与判级函数（表 11~15 + 6.1.4.3 综合评级）。

等级统一用整数 1~4 表示 Ⅰ~Ⅳ 级。所有长度单位为 mm。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple, Union

GRADE_LABELS = {1: "Ⅰ级", 2: "Ⅱ级", 3: "Ⅲ级", 4: "Ⅳ级"}

# 外径 ≤ 100mm 为小径管（评定区固定 10×10）
SMALL_PIPE_MAX_OD_MM = 100.0


def grade_label(grade: Optional[int]) -> str:
    return GRADE_LABELS.get(grade, "") if grade else ""


# ---------------------------------------------------------------------------
# 规格解析（《影像信息表》“规格”列）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WeldSpec:
    """thickness 为评级用的母材公称厚度 T。"""

    thickness: float
    is_pipe: bool = False
    outer_diameter: Optional[float] = None
    extra_thickness: Optional[float] = None  # “20+4” 中的垫板/复合层厚度
    raw: str = ""

    @property
    def is_small_pipe(self) -> bool:
        return self.is_pipe and self.outer_diameter is not None and self.outer_diameter <= SMALL_PIPE_MAX_OD_MM

    @property
    def actual_outer_diameter(self) -> float:
        """返回管件公称规格对应的实际标准外径 (mm)。
        在钢管系列 1（通用/国际标准系列，如 GB/T 17395 等）中：
        Φ48 公称外径实际为 48.3mm (DN40 / 1.5寸管)；
        Φ60 为 60.3mm；Φ76 为 76.1mm；Φ89 为 88.9mm；Φ114 为 114.3mm；Φ219 为 219.1mm。
        """
        if self.outer_diameter is None:
            return 0.0
        od = self.outer_diameter
        if abs(od - 48.0) < 0.5:
            return 48.3
        if abs(od - 60.0) < 0.5:
            return 60.3
        if abs(od - 76.0) < 0.5:
            return 76.1
        if abs(od - 89.0) < 0.5:
            return 88.9
        if abs(od - 114.0) < 0.5:
            return 114.3
        if abs(od - 219.0) < 0.5:
            return 219.1
        return od

    @property
    def chapter(self) -> int:
        """带 Φ 或 D*t 的按第 7 章（管），否则按第 6 章（承压设备本体）。"""
        return 7 if self.is_pipe else 6


_NUM = r"(\d+(?:\.\d+)?)"
# 管规格：带或不带 Φ/φ/Ø/D/DN 前缀，乘号支持 × / x / X / * / ＊，如 "Φ89×6"、"219*7"、"356*5"
_PIPE_RE = re.compile(r"(?:[ΦφØøϕ⌀Dd]|(?:DN|dn))?\s*" + _NUM + r"\s*[×xX*＊]\s*" + _NUM)
# 板规格：如 "16"、"20"、"20+4"、"T=16"
_PLATE_RE = re.compile(r"^(?:[TtδHh]\s*[:=]?\s*)?" + _NUM + r"(?:\s*\+\s*" + _NUM + r")?$")


def parse_spec(value: Union[str, int, float]) -> WeldSpec:
    """解析 “28” / “20+4” / “Φ89×6” / “219*7” 等规格。“20+4” 取 T=20（垫板/复合层不计入母材厚度）。"""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return WeldSpec(thickness=float(value), raw=str(value))
    text = str(value or "").strip()
    norm = text.replace("（", "(").replace("）", ")").replace("ｍｍ", "").replace("mm", "").replace("MM", "")
    norm = norm.replace("＋", "+").replace(" ", "")
    multipliers = sum(norm.count(op) for op in ("*", "×", "x", "X", "＊"))
    if multipliers > 1:
        raise ValueError(f"无法解析规格: {text!r}")
    m = _PIPE_RE.search(norm)
    if m:
        return WeldSpec(thickness=float(m.group(2)), is_pipe=True, outer_diameter=float(m.group(1)), raw=text)
    m = _PLATE_RE.match(norm)
    if m:
        extra = float(m.group(2)) if m.group(2) else None
        return WeldSpec(thickness=float(m.group(1)), extra_thickness=extra, raw=text)
    raise ValueError(f"无法解析规格: {text!r}")


# ---------------------------------------------------------------------------
# 圆形缺陷：表 11 评定区、表 12 点数换算、表 13 分级、表 14 不计点数
# ---------------------------------------------------------------------------

def round_zone_mm(spec: WeldSpec) -> Tuple[float, float]:
    """返回 (沿焊缝方向长度, 垂直焊缝方向宽度)。评定区长边平行于焊缝。"""
    t = spec.thickness
    if spec.is_small_pipe or t <= 25:
        return 10.0, 10.0
    if t <= 100:
        return 20.0, 10.0
    return 30.0, 10.0


def round_ignore_diameter_mm(thickness: float) -> float:
    """表 14：长径 ≤ 该值的圆形缺陷不计点数。"""
    if thickness <= 25:
        return 0.5
    if thickness <= 50:
        return 0.7
    return 0.014 * thickness


_POINTS_TABLE: Sequence[Tuple[float, int]] = (
    (1.0, 1), (2.0, 2), (3.0, 3), (4.0, 6), (6.0, 10), (8.0, 15),
)


def round_points(diameter_mm: float, thickness: float) -> int:
    """表 12 点数换算（已先按表 14 过滤，不计点数时返回 0）。"""
    diameter_mm = round(diameter_mm, 3)  # 消除像素↔mm 换算的浮点误差（如 2.0000001 落入下一档）
    if diameter_mm <= round_ignore_diameter_mm(thickness):
        return 0
    for upper, points in _POINTS_TABLE:
        if diameter_mm <= upper:
            return points
    return 25


# (T 上限, (Ⅰ, Ⅱ, Ⅲ 级允许点数))
_ROUND_LIMITS: Sequence[Tuple[float, Tuple[int, int, int]]] = (
    (10, (1, 3, 6)),
    (15, (2, 6, 12)),
    (25, (3, 9, 18)),
    (50, (4, 12, 24)),
    (100, (5, 15, 30)),
    (math.inf, (6, 18, 36)),
)


def round_limits(thickness: float) -> Tuple[int, int, int]:
    for upper, limits in _ROUND_LIMITS:
        if thickness <= upper:
            return limits
    return _ROUND_LIMITS[-1][1]


def round_single_diameter_limit_mm(thickness: float, grade: int) -> float:
    """表 13 单个圆形缺陷最大长径：
    Ⅰ级：<= 0.35 T，且最大不超过 5.0 mm；
    Ⅱ级：<= 0.45 T，且最大不超过 7.0 mm；
    Ⅲ级：<= 0.50 T，且最大不超过 8.0 mm。
    """
    if grade == 1:
        return min(0.35 * thickness, 5.0)
    if grade == 2:
        return min(0.45 * thickness, 7.0)
    if grade == 3:
        return min(0.50 * thickness, 8.0)
    return math.inf


def round_grade(points: int, max_diameter_mm: float, thickness: float) -> int:
    """表 13 圆形缺陷分级：同时受评定区点数与单个缺陷最大长径双重约束。"""
    limit_3 = round_single_diameter_limit_mm(thickness, 3)
    if max_diameter_mm > limit_3:
        return 4
    for grade, limit in zip((1, 2, 3), round_limits(thickness)):
        d_limit = round_single_diameter_limit_mm(thickness, grade)
        if points <= limit and max_diameter_mm <= d_limit:
            return grade
    return 4


def round_grade_with_ignored(points: int, max_diameter_mm: float, thickness: float,
                             ignored_count: int = 0) -> Tuple[int, Optional[str]]:
    """表 13 圆形缺陷分级，并结合表 14 备注 / 6.1.4.2 降级规则：
    - 基础级别按点数和长径查表 13；
    - Ⅰ 级评定区内不计点数圆形缺陷 > 10 个降为 Ⅱ 级；
    - T <= 5mm 的 Ⅱ 级评定区内不计点数圆形缺陷 > 10 个降为 Ⅲ 级。
    返回 (最终等级, 降级原因说明)。
    """
    base_grade = round_grade(points, max_diameter_mm, thickness)
    if base_grade == 1 and ignored_count > 10:
        return 2, f"评定区内不计点数圆形缺陷共 {ignored_count} 个(>10个)，由 Ⅰ 级降为 Ⅱ 级"
    if base_grade == 2 and thickness <= 5.0 and ignored_count > 10:
        return 3, f"厚度 T={thickness}mm<=5mm 且不计点数圆形缺陷共 {ignored_count} 个(>10个)，由 Ⅱ 级降为 Ⅲ 级"
    return base_grade, None


# ---------------------------------------------------------------------------
# 条形缺陷：表 15
# ---------------------------------------------------------------------------

def strip_band_width_mm(thickness: float) -> float:
    """表 15 注 2：条形缺陷评定区宽度。"""
    if thickness <= 25:
        return 4.0
    if thickness <= 100:
        return 6.0
    return 8.0


def strip_single_limit_mm(thickness: float, grade: int) -> float:
    if grade == 2:
        return min(max(thickness / 3, 4.0), 20.0)
    if grade == 3:
        return min(max(2 * thickness / 3, 6.0), 30.0)
    raise ValueError("条形缺陷只有 Ⅱ/Ⅲ 级有限值")


def strip_group_params(thickness: float, grade: int) -> Tuple[float, float, float]:
    """返回 (评定区长度, 相邻间距系数 k（间距 ≤ k·L）, 累计长度限值)。"""
    if grade == 2:
        return 12 * thickness, 6.0, max(thickness, 4.0)
    if grade == 3:
        return 6 * thickness, 3.0, max(thickness, 6.0)
    raise ValueError("条形缺陷只有 Ⅱ/Ⅲ 级有限值")


Segment = Tuple[float, float]  # 沿焊缝方向 (start, end)，mm


def strip_chains(items: Sequence, gap_factor: float,
                 span: Callable[[object], Segment] = lambda s: s) -> list:
    """把同一直线上的条形缺陷按“相邻间距 ≤ k·L（L 为组内最长缺陷）”串成组。

    items 可以是 (start, end) 元组，也可以是任意对象（用 span 取其沿焊缝区间）。
    """
    ordered = sorted(items, key=span)
    chains: list = []
    for item in ordered:
        s, e = span(item)
        if chains:
            chain = chains[-1]
            spans = [span(c) for c in chain]
            longest = max(max(ce - cs for cs, ce in spans), e - s)
            gap = s - max(ce for _, ce in spans)
            if gap <= gap_factor * longest:
                chain.append(item)
                continue
        chains.append([item])
    return chains


def _groups_within_limit(segments: Sequence[Segment], thickness: float, grade: int) -> bool:
    zone_len, gap_factor, total_limit = strip_group_params(thickness, grade)
    for chain in strip_chains(segments, gap_factor):
        if len(chain) < 2:
            continue
        for start, _ in chain:
            window_end = start + zone_len
            # 与评定区相交的缺陷按全长计入（偏严）
            total = sum(e - s for s, e in chain if s < window_end and e > start)
            if total > total_limit:
                return False
    return True


def strip_grade(segments: Sequence[Segment], thickness: float) -> int:
    """同一条形缺陷评定区（同一直线）内的条形缺陷分级；Ⅰ 级不允许条形缺陷。"""
    if not segments:
        return 1
    for grade in (2, 3):
        limit = strip_single_limit_mm(thickness, grade)
        if all(e - s <= limit for s, e in segments) and _groups_within_limit(segments, thickness, grade):
            return grade
    return 4


# ---------------------------------------------------------------------------
# 综合评级 / 管道根部缺陷
# ---------------------------------------------------------------------------

def comprehensive_grade(round_g: int, strip_g: int) -> int:
    """6.1.4.3：两者级别之和减一，超过 Ⅲ 级即 Ⅳ 级。"""
    return min(4, round_g + strip_g - 1)


def pipe_root_length_limit_mm(spec: WeldSpec) -> float:
    """NB/T 47013.2-2015 第 7 章管道根部内凹/咬边 Ⅲ 级累计长度限值 (mm)。

    竞赛规则第（9）条规定：管道类的根部内凹和根部咬边的深度在评级时不予考虑，
    均按长度评级，由于 Ⅱ 级和 Ⅲ 级允许的长度一样，当缺陷总长度 > Ⅲ 级时评为 Ⅳ，其余情况评定为 Ⅱ 级。
    - 表 27（小径管，Do <= 100mm）：累计总长度与焊缝总长度的比值 <= 30%（周长以 π*Do 计算）；
    - 表 26（大中径管，Do > 100mm）：允许累计总长度不超过 100mm。
    """
    if not spec.is_pipe:
        return 0.0
    if spec.is_small_pipe and spec.outer_diameter:
        return math.pi * spec.outer_diameter * 0.3
    return 100.0


def small_pipe_defect_length_mm(proj_length_mm: float, spec: WeldSpec) -> float:
    """小径管（Do <= 100mm）双壁双影/双壁单影透照下，缺陷弧长展开定量。

    在小径管环焊缝透照底片上，底片平面投影的是 3D 圆柱面上的环缝。
    单次透照所能覆盖的焊缝有效范围为半圆周（180°弧长，L_half = 1.571 * Do）。
    当根部缺陷（未焊透、未熔合等）或条形缺陷贯穿整个透照管影（投影跨度 >= 0.75 * Do）时，
    物理上该缺陷贯穿了整个曝光半圆周，评定定量应取展开半圆周弧长：
        L = round(1.571 * Do, 2)  (例如 Φ48x5 管件，L = 1.571 * 48.3 = 75.88mm)
    当缺陷为局部缺陷时，投影弦长映射为圆周弧长：
        L = min(round(proj_length_mm * (math.pi / 2.0), 1), half_circ)
    """
    if not spec.is_small_pipe or spec.outer_diameter is None or spec.outer_diameter <= 0:
        return proj_length_mm

    od = spec.actual_outer_diameter
    half_circ = round(1.571 * od, 2)  # 标准 4 位系数 1.571 (π/2)

    # 贯穿性缺陷：若投影跨度达到管外径的 75% 时视为全半周贯穿
    if proj_length_mm >= 0.75 * spec.outer_diameter:
        return half_circ

    # 局部缺陷：按投影放大系数展开，上限为半圆周
    arc_len = round(proj_length_mm * (math.pi / 2.0), 1)
    return min(arc_len, half_circ)


def max_window_length(segments: Sequence[Segment], window_mm: float) -> float:
    """任意长度为 window_mm 的区间内，各缺陷落在区间内部分的累计长度最大值。"""
    best = 0.0
    starts = {s for s, _ in segments} | {e - window_mm for _, e in segments}
    for w0 in starts:
        w1 = w0 + window_mm
        best = max(best, sum(max(0.0, min(e, w1) - max(s, w0)) for s, e in segments))
    return best


def pipe_root_grade_table26(segments: Sequence[Segment], thickness: float, limit_iii_mm: float = 100.0) -> int:
    """表 26（Do > 100mm）严格按长度分级（深度不计）：任意 3T 范围内累计 ≤ T 为 Ⅱ 级；
    否则总长 ≤ limit_iii_mm 为 Ⅲ 级；超过为 Ⅳ 级。segments 为沿焊缝方向 (start, end)，同一焊缝。"""
    if sum(e - s for s, e in segments) > limit_iii_mm:
        return 4
    if max_window_length(segments, 3 * thickness) <= thickness:
        return 2
    return 3


def pipe_root_grade(total_length_mm: float, limit_iii_mm: Optional[float]) -> int:
    """竞赛规则（9）：管道根部内凹/咬边不计深度，总长 > Ⅲ 级限值为 Ⅳ 级，其余为 Ⅱ 级。"""
    if limit_iii_mm is not None and total_length_mm > limit_iii_mm:
        return 4
    return 2
