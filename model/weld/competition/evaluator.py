"""把单张图的推理结果转换为竞赛填报项：缺陷定位(X)、定性、定量、评定等级。

流程：
1. 取各 ROI 的检测框，映射为竞赛缺陷类型（“其他”丢弃）；焊缝方向由 ROI 长边决定。
   圆形/条形按标准 3.6/3.7 用长宽比复核（≤3 为圆形，>3 为条形）。
2. 按竞赛规则合并：
   - 横向密集裂纹 → 一个缺陷，长度取最长一条；
   - 纵向（沿焊缝）断续裂纹/未熔合/未焊透：间隔 ≤ intermittent_merge_gap_mm 视为一个缺陷，长度含间隔；
   - 条形缺陷：同一直线且间距 ≤ 较短缺陷长度 → 一个缺陷（表 15 注 3，间距计入长度）；
     满足表 15 组判定条件的条渣组 → 按一个缺陷填写，长度为组内累计长度；
   - 圆形缺陷：在评定区窗口内滑动，取点数最多的评定区；Ⅰ 级（T≤5 时含 Ⅱ 级）评定区内
     不计点数的缺陷多于 10 个时降一级（6.1.5.4）；
     该类评定区内同时存在条形缺陷时改为“综合评级”，定量为 “长度, 点数”。
3. 定位 X = 组成该缺陷（或评定框内计点）各检测框在原始影像坐标系中的最小 x。
4. 等级：裂纹/未熔合/未焊透 Ⅳ 级；圆形查表 13；条形查表 15；综合评级 R圆+R条-1；
   整图取各类中最低（数值最大）的级别（6.1.4.4）。
"""

from __future__ import annotations

import bisect
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import standards as std
from .geometry import (Box, axis_span, box_to_original, cross_axis, defect_dimensions_px,
                       defect_length_px, original_size, overlaps)

PIXEL_SIZE_MM = 0.042

CRACK = "裂纹"
LACK_OF_FUSION = "未熔合"
LACK_OF_PENETRATION = "未焊透"
STRIP = "条形缺陷"
ROUND = "圆形缺陷"
ROOT_CONCAVE = "根部内凹"
ROOT_UNDERCUT = "根部咬边"
COMPREHENSIVE = "综合评级"

FATAL_TYPES = (CRACK, LACK_OF_FUSION, LACK_OF_PENETRATION)

# 模型类别名 → 竞赛缺陷定性（中文为当前主模型 CLASS_NAMES，英文为兼容别名）
LABEL_TO_TYPE: Dict[str, Optional[str]] = {
    "裂纹": CRACK, "crack": CRACK,
    "未熔合": LACK_OF_FUSION, "lack_fusion": LACK_OF_FUSION, "lack_of_fusion": LACK_OF_FUSION,
    "未焊透": LACK_OF_PENETRATION, "incomplete_penetration": LACK_OF_PENETRATION,
    "lack_of_penetration": LACK_OF_PENETRATION,
    "条形缺陷": STRIP, "linear_defect": STRIP, "slag": STRIP,
    "圆形缺陷": ROUND, "round_defect": ROUND, "porosity": ROUND,
    "内凹": ROOT_CONCAVE, "根部内凹": ROOT_CONCAVE, "concave": ROOT_CONCAVE,
    "咬边": ROOT_UNDERCUT, "根部咬边": ROOT_UNDERCUT, "undercut": ROOT_UNDERCUT,
    "其他": None, "other": None,
}


@dataclass
class EvalConfig:
    pixel_size_mm: float = PIXEL_SIZE_MM
    min_confidence: float = 0.0
    # 横向裂纹沿焊缝方向间距 ≤ 该值视为“密集”，合并为一个缺陷
    crack_cluster_gap_mm: float = 2.0
    # 断续未熔合/未焊透/纵向裂纹：间隔 ≤ 该值视为一个缺陷，间隔“非常明显”时单独记录（规则（7）(d)/(8)(b)）。
    # 不用表 15 注 3 的“间距 ≤ 较短缺陷长度”：真实底片上会把相隔 40mm 的两段长未熔合合并
    intermittent_merge_gap_mm: float = 2.0
    # 合并后的长度："envelope" 包络长度（含间隔，同表 15 注 3）；"sum" 各段长度之和（不含间隔）
    intermittent_length_mode: str = "envelope"
    # 条渣组按哪个级别的组判定条件（2: 12T/6L，3: 6T/3L）合并为一个缺陷填写
    strip_group_report_grade: int = 2
    # 管道根部内凹/咬边 Ⅲ 级允许的累计长度（mm）；None 时按第 7 章自动取（表 27：0.3πDo，表 26：100mm）
    pipe_root_length_limit_iii_mm: Optional[float] = None
    # 大中径管（Do > 100）根部内凹/咬边严格按表 26 分 Ⅱ/Ⅲ/Ⅳ 级（任意 3T 内累计 ≤ T 为 Ⅱ 级）。
    # 默认 False：按竞赛规则（9）字面执行，超 Ⅲ 级限值判 Ⅳ，其余判 Ⅱ（待组委会确认）
    pipe_root_strict_table26: bool = False
    quantity_separator: str = ", "
    # 圆形/条形缺陷按长宽比（标准 3.6/3.7：≤3 为圆形）复核模型给出的类别
    reclassify_by_aspect: bool = True
    round_max_aspect: float = 3.0
    # Ⅰ 级（及 T≤5 的 Ⅱ 级）评定区内不计点数缺陷多于该数量时降一级
    ignored_round_max_count: int = 10
    # 圆形缺陷框内精细拆分（需传入图像，见 pore_split）：密集气孔大框拆回逐个气孔、按真实轮廓量长径
    split_round_clusters: bool = False
    # 第 6 章（板）上检出的根部内凹/咬边："drop" 不填报（默认：第 6 章不对其分级，且真实底片上多为贯穿整条
    # 焊缝的误检）；"report" 填报但不分级（组委会要求板上也填报时切换）
    plate_root_defects: str = "drop"
    # 方向矫正置信度低于该值时给出提示（定位 X 由同一 label 逆变换，不受方向判错影响）
    min_correction_confidence: float = 0.85


@dataclass
class DefectRecord:
    defect_type: str
    x_px: int
    x_mm: float
    quantity: str
    grade: Optional[int]
    grade_label: str
    length_mm: Optional[float] = None
    points: Optional[int] = None
    aspect_ratio: Optional[float] = None
    member_count: int = 1
    roi_index: int = 0
    bbox_original: List[float] = field(default_factory=list)


@dataclass
class ImageEvaluation:
    image_path: str
    spec: str
    grade: int
    grade_label: str
    records: List[DefectRecord]
    warnings: List[str]

    @property
    def image_name(self) -> str:
        return Path(self.image_path).name

    @property
    def has_defects(self) -> bool:
        return bool(self.records)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["image_name"] = self.image_name
        data["has_defects"] = self.has_defects
        return data

    def to_submission_records(self, fill_no_defect: bool = True) -> List[Dict[str, Any]]:
        """生成符合竞赛提交规范的缺陷记录列表。
        当无缺陷（评为 Ⅰ 级）且 fill_no_defect=True 时，生成一条标准合格记录。
        """
        if not self.records and fill_no_defect:
            return [{
                "image_name": self.image_name,
                "defect_index": 1,
                "defect_type": "无",
                "x_px": "—",
                "x_mm": "—",
                "quantity": "—",
                "grade": 1,
                "grade_label": "Ⅰ级",
                "is_no_defect": True,
            }]
        out: List[Dict[str, Any]] = []
        for idx, r in enumerate(self.records, start=1):
            out.append({
                "image_name": self.image_name,
                "defect_index": idx,
                "defect_type": r.defect_type,
                "x_px": r.x_px,
                "x_mm": r.x_mm,
                "quantity": r.quantity,
                "grade": r.grade,
                "grade_label": r.grade_label,
                "length_mm": r.length_mm,
                "points": r.points,
                "aspect_ratio": r.aspect_ratio,
                "is_no_defect": False,
            })
        return out


# ---------------------------------------------------------------------------
# 内部数据结构
# ---------------------------------------------------------------------------

@dataclass
class _Det:
    dtype: str
    box: Box  # 矫正后坐标，像素
    length_mm: float
    roi: int
    axis: str
    a: Tuple[float, float]  # 沿焊缝区间（mm）
    c: Tuple[float, float]  # 垂直焊缝区间（mm）
    aspect_ratio: float = 1.0


@dataclass
class _Piece:
    """合并后的一个缺陷（可能由多个检测框组成）。"""
    dtype: str
    members: List[_Det]
    length_mm: float
    roi: int
    a: Tuple[float, float]
    c: Tuple[float, float]


def _piece(det: _Det) -> _Piece:
    return _Piece(det.dtype, [det], det.length_mm, det.roi, det.a, det.c)


def _span_union(x: Tuple[float, float], y: Tuple[float, float]) -> Tuple[float, float]:
    return min(x[0], y[0]), max(x[1], y[1])


def _collinear(p: _Piece, q: _Piece, band_mm: float) -> bool:
    """同一直线：垂直焊缝方向区间重叠，或中心线偏差不超过半个条形评定区宽度。"""
    if overlaps(p.c, q.c):
        return True
    return abs((p.c[0] + p.c[1]) / 2 - (q.c[0] + q.c[1]) / 2) <= band_mm / 2


def _merge_collinear(pieces: List[_Piece], band_mm: float, gap_limit) -> List[_Piece]:
    """反复合并同一直线、沿焊缝间距 ≤ gap_limit(p, q) 的缺陷；合并后长度为包络长度（间隔计入）。"""
    pieces = sorted(pieces, key=lambda p: p.a)
    changed = True
    while changed:
        changed = False
        out: List[_Piece] = []
        for p in pieces:
            for m in out:
                if m.roi != p.roi or not _collinear(m, p, band_mm):
                    continue
                gap = max(p.a[0], m.a[0]) - min(p.a[1], m.a[1])
                if gap <= gap_limit(m, p):
                    m.members.extend(p.members)
                    m.a = _span_union(m.a, p.a)
                    m.c = _span_union(m.c, p.c)
                    m.length_mm = max(m.a[1] - m.a[0], m.length_mm, p.length_mm)
                    changed = True
                    break
            else:
                out.append(p)
        pieces = sorted(out, key=lambda p: p.a)
    return pieces


def _bands(pieces: List[_Piece], band_mm: float) -> List[List[_Piece]]:
    """按“同一直线”把条形缺陷分到各条形缺陷评定区（连通分量）。"""
    parent = list(range(len(pieces)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            if pieces[i].roi == pieces[j].roi and _collinear(pieces[i], pieces[j], band_mm):
                parent[find(j)] = find(i)
    groups: Dict[int, List[_Piece]] = {}
    for i, p in enumerate(pieces):
        groups.setdefault(find(i), []).append(p)
    return list(groups.values())


def _fmt_mm(value: float) -> str:
    return f"{value:.1f}"


@dataclass
class _Window:
    roi: int
    pores: List[Tuple[_Det, int, float]]  # (检测框, 点数, 长径)；点数 0 为不计点数缺陷
    strips: List[_Piece]
    points: int
    max_d: float
    grade: int

    @property
    def counted(self) -> List[_Det]:
        return [p[0] for p in self.pores if p[1] > 0]

    @property
    def ignored_count(self) -> int:
        return sum(1 for p in self.pores if p[1] == 0)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def _collect(result: Mapping[str, Any], cfg: EvalConfig, warnings: List[str], image=None,
             strip_band_mm: float = float("inf")) -> List[_Det]:
    px = cfg.pixel_size_mm
    dets: List[_Det] = []
    splitter = None
    if cfg.split_round_clusters and image is not None:
        from .pore_split import split_pores as splitter
    for roi_idx, roi in enumerate(result.get("rois") or []):
        rb = roi.get("bbox") or []
        axis = "y" if len(rb) == 4 and (rb[3] - rb[1]) > (rb[2] - rb[0]) else "x"
        for d in (roi.get("detections") or roi.get("defects") or []):
            name = str(d.get("class_name", "")).strip()
            key = name if name in LABEL_TO_TYPE else name.lower()
            if key not in LABEL_TO_TYPE:
                warnings.append(f"未知缺陷类别已忽略: {name}")
                continue
            dtype = LABEL_TO_TYPE[key]
            if dtype is None:
                continue
            conf = d.get("confidence", d.get("conf"))
            if isinstance(conf, (int, float)) and conf < cfg.min_confidence:
                continue
            box = d.get("bbox")
            if not box or len(box) != 4:
                continue
            box_t = tuple(float(v) for v in box)
            major_px, minor_px, aspect = defect_dimensions_px(box_t, d.get("polygon"))
            roi_i = int(roi.get("roi_index", roi_idx))
            # 模型给“圆形缺陷”的框先尝试框内拆分（大框常是一片气孔，按框长宽比会被误判成超长条形缺陷）；
            # 拆不出可信气孔时再按长宽比复核
            subs = splitter(image, box_t) if splitter is not None and dtype == ROUND else None
            if not subs and cfg.reclassify_by_aspect and dtype in (ROUND, STRIP):
                new_type = STRIP if aspect > cfg.round_max_aspect else ROUND
                # 短边超过条形缺陷评定区宽度（表 15 注 2）的“圆形缺陷”大框是一片气孔，不可能是单个条形缺陷
                if new_type == STRIP and dtype == ROUND and minor_px * px > strip_band_mm:
                    new_type = ROUND
                if new_type != dtype:
                    warnings.append(f"{dtype}长宽比 {aspect:.1f}，按标准改判为{new_type}")
                    dtype = new_type
            if subs:
                if len(subs) > 1:
                    warnings.append(f"圆形缺陷框（{(box_t[2] - box_t[0]) * px:.1f}×{(box_t[3] - box_t[1]) * px:.1f}mm）"
                                    f"框内拆分为 {len(subs)} 个气孔")
                for sb in subs:
                    sw, sh = sb[2] - sb[0], sb[3] - sb[1]
                    dets.append(_Det(ROUND, sb, max(sw, sh) * px, roi_i, axis,
                                     tuple(v * px for v in axis_span(sb, axis)),
                                     tuple(v * px for v in axis_span(sb, cross_axis(axis))),
                                     aspect_ratio=round(max(sw, sh) / max(min(sw, sh), 1.0), 2)))
                continue
            length_mm = defect_length_px(box_t, d.get("polygon"), straight=(dtype == CRACK)) * px
            a = tuple(v * px for v in axis_span(box_t, axis))
            c = tuple(v * px for v in axis_span(box_t, cross_axis(axis)))
            dets.append(_Det(dtype, box_t, length_mm, roi_i, axis, a, c, aspect_ratio=round(aspect, 2)))
    return dets


def _union_length(spans: Iterable[Tuple[float, float]]) -> float:
    total, end = 0.0, float("-inf")
    for s, e in sorted(spans):
        if e > end:
            total += e - max(s, end)
            end = e
    return total


def _round_windows(pores: List[Tuple[_Det, int, float]], strips: List[_Piece],
                   spec: std.WeldSpec, cfg: EvalConfig) -> List[_Window]:
    """枚举以缺陷边缘为边界的评定区窗口。pores 含不计点数缺陷（点数 0）。"""
    zone_a, zone_c = std.round_zone_mm(spec)
    t = spec.thickness
    windows: List[_Window] = []
    for roi in sorted({p[0].roi for p in pores}):
        roi_pores = sorted((p for p in pores if p[0].roi == roi), key=lambda p: p[0].a[0])
        # 不计点数缺陷只在数量可能超限时参与定窗
        anchor_all = sum(1 for p in roi_pores if p[1] == 0) > cfg.ignored_round_max_count
        anchors = [p for p in roi_pores if p[1] > 0 or anchor_all]
        a_starts = [p[0].a[0] for p in roi_pores]
        max_len_a = max((p[0].a[1] - p[0].a[0] for p in roi_pores), default=0.0)
        roi_strips = [s for s in strips if s.roi == roi]
        seen = set()
        for sa in sorted({p[0].a[0] for p in anchors} | {p[0].a[1] - zone_a for p in anchors}):
            wa = (sa, sa + zone_a)
            lo = bisect.bisect_left(a_starts, sa - max_len_a)
            hi = bisect.bisect_left(a_starts, wa[1])
            in_a = [p for p in roi_pores[lo:hi] if overlaps(p[0].a, wa)]
            if not in_a:
                continue
            c_anchors = [p for p in in_a if p[1] > 0 or anchor_all]
            for sc in {p[0].c[0] for p in c_anchors} | {p[0].c[1] - zone_c for p in c_anchors}:
                wc = (sc, sc + zone_c)
                # 与评定区边界相割的缺陷划入评定区
                inside = [p for p in in_a if overlaps(p[0].c, wc)]
                in_strips = [s for s in roi_strips if overlaps(s.a, wa) and overlaps(s.c, wc)]
                key = (frozenset(id(p[0]) for p in inside), frozenset(id(s) for s in in_strips))
                if key in seen:
                    continue
                seen.add(key)
                counted = [p for p in inside if p[1] > 0]
                ignored = len(inside) - len(counted)
                if not counted and ignored <= cfg.ignored_round_max_count:
                    continue
                points = sum(p[1] for p in counted)
                max_d = max((p[2] for p in counted), default=0.0)
                grade = std.round_grade(points, max_d, t)
                if ignored > cfg.ignored_round_max_count and (grade == 1 or (grade == 2 and t <= 5)):
                    grade += 1
                windows.append(_Window(roi, inside, in_strips, points, max_d, grade))
    return windows


def evaluate_image(result: Mapping[str, Any], spec: Union[std.WeldSpec, str, int, float],
                   config: Optional[EvalConfig] = None, image=None) -> ImageEvaluation:
    """image：与检测坐标系一致（方向矫正后）的灰度图，仅 split_round_clusters 时使用。"""
    cfg = config or EvalConfig()
    spec = spec if isinstance(spec, std.WeldSpec) else std.parse_spec(spec)
    t = spec.thickness
    warnings: List[str] = []

    label = int((result.get("correction") or {}).get("label", 0) or 0)
    corr_w, corr_h = int(result.get("width") or 0), int(result.get("height") or 0)
    orig_w, orig_h = original_size(corr_w, corr_h, label)
    if label and not (corr_w and corr_h):
        warnings.append("推理结果缺少图像尺寸，无法还原原始坐标")
    corr_conf = (result.get("correction") or {}).get("confidence")
    if isinstance(corr_conf, (int, float)) and corr_conf < cfg.min_correction_confidence:
        warnings.append(f"方向矫正置信度 {corr_conf:.2f} 偏低（label={label}）：定位 X 不受影响，检出率可能受影响")

    def make_record(dtype: str, members: Iterable[_Det], quantity: str, grade: Optional[int],
                    length: Optional[float] = None, points: Optional[int] = None) -> DefectRecord:
        members = list(members)
        boxes = [box_to_original(m.box, label, orig_w, orig_h) for m in members]
        x_px = min(b[0] for b in boxes)
        bbox = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes)]
        ar = members[0].aspect_ratio if len(members) == 1 else None
        return DefectRecord(
            defect_type=dtype, x_px=int(round(x_px)), x_mm=round(x_px * cfg.pixel_size_mm, 2),
            quantity=quantity, grade=grade, grade_label=std.grade_label(grade),
            length_mm=round(length, 1) if length is not None else None, points=points,
            aspect_ratio=ar,
            member_count=len(members), roi_index=members[0].roi,
            bbox_original=[round(v, 1) for v in bbox],
        )

    dets = _collect(result, cfg, warnings, image, std.strip_band_width_mm(t))
    records: List[DefectRecord] = []
    grades: List[int] = []
    band_mm = std.strip_band_width_mm(t)

    # ---- 裂纹 / 未熔合 / 未焊透 ----------------------------------------------
    cracks = [d for d in dets if d.dtype == CRACK]
    transverse = [d for d in cracks if (d.c[1] - d.c[0]) > (d.a[1] - d.a[0])]
    clusters: List[List[_Det]] = []
    for d in sorted(transverse, key=lambda d: (d.roi, d.a)):
        last = clusters[-1] if clusters else None
        if last and last[0].roi == d.roi and d.a[0] - max(m.a[1] for m in last) <= cfg.crack_cluster_gap_mm:
            last.append(d)
        else:
            clusters.append([d])
    for cluster in clusters:
        longest = max(m.length_mm for m in cluster)
        records.append(make_record(CRACK, cluster, _fmt_mm(longest), 4, length=longest))

    for dtype in (CRACK, LACK_OF_FUSION, LACK_OF_PENETRATION):
        pieces = [_piece(d) for d in dets if d.dtype == dtype and not (dtype == CRACK and d in transverse)]
        for p in _merge_collinear(pieces, band_mm, lambda m, q: cfg.intermittent_merge_gap_mm):
            length = p.length_mm
            if len(p.members) > 1 and cfg.intermittent_length_mode == "sum":
                length = _union_length(m.a for m in p.members)
            records.append(make_record(dtype, p.members, _fmt_mm(length), 4, length=length))
    if any(r.defect_type in FATAL_TYPES for r in records):
        grades.append(4)

    # ---- 条形缺陷（表 15 注 3 合并）---------------------------------------------
    strips = _merge_collinear([_piece(d) for d in dets if d.dtype == STRIP], band_mm,
                              lambda m, q: min(m.length_mm, q.length_mm))
    strip_band_grade: Dict[int, int] = {}
    for band in _bands(strips, band_mm):
        g = std.strip_grade([(p.a[0], p.a[0] + p.length_mm) for p in band], t)
        grades.append(g)
        for p in band:
            strip_band_grade[id(p)] = g

    # ---- 圆形缺陷 / 综合评级 ---------------------------------------------------
    pores = [(d, std.round_points(d.length_mm, t), d.length_mm) for d in dets if d.dtype == ROUND]
    ignored = sum(1 for p in pores if p[1] == 0)
    if ignored:
        warnings.append(f"{ignored} 个圆形缺陷长径 ≤ {std.round_ignore_diameter_mm(t):.2f}mm，不计点数")

    absorbed: set = set()
    windows = _round_windows(pores, strips, spec, cfg)
    if windows:
        worst_round = max(windows, key=lambda w: (w.grade, w.points, w.max_d))
        grades.append(worst_round.grade)
        mixed = [w for w in windows if w.strips]
        if mixed:
            def comp_of(w: _Window) -> int:
                sg = std.strip_grade([(s.a[0], s.a[0] + s.length_mm) for s in w.strips], t)
                return std.comprehensive_grade(w.grade, sg)

            best = max(mixed, key=lambda w: (comp_of(w), w.points, w.max_d))
            comp_g = comp_of(best)
            grades.append(comp_g)
            strip_len = sum(s.length_mm for s in best.strips)
            members = (best.counted or [p[0] for p in best.pores]) + [m for s in best.strips for m in s.members]
            qty = f"{_fmt_mm(strip_len)}{cfg.quantity_separator}{best.points}"
            records.append(make_record(COMPREHENSIVE, members, qty, comp_g, length=strip_len, points=best.points))
            absorbed = {id(s) for s in best.strips}
        else:
            if worst_round.ignored_count > cfg.ignored_round_max_count:
                warnings.append(f"评定区内不计点数缺陷 {worst_round.ignored_count} 个（>"
                                f"{cfg.ignored_round_max_count}），等级降一级")
            records.append(make_record(ROUND, worst_round.counted or [p[0] for p in worst_round.pores],
                                       str(worst_round.points),
                                       worst_round.grade, points=worst_round.points))

    # ---- 条形缺陷填报（条渣组按一个缺陷）--------------------------------------
    remaining = [p for p in strips if id(p) not in absorbed]
    _, gap_factor, _ = std.strip_group_params(t, cfg.strip_group_report_grade)
    for band in _bands(remaining, band_mm):
        for chain in std.strip_chains(band, gap_factor, span=lambda p: (p.a[0], p.a[0] + p.length_mm)):
            total = sum(p.length_mm for p in chain)
            g = max(strip_band_grade[id(p)] for p in chain)
            records.append(make_record(STRIP, [m for p in chain for m in p.members], _fmt_mm(total), g,
                                       length=total))

    # ---- 根部内凹 / 根部咬边 ---------------------------------------------------
    # 同类重叠/相接的检测框（切片拼接残留）合并为一个缺陷，避免长度重复计算
    roots = [p for dtype in (ROOT_CONCAVE, ROOT_UNDERCUT)
             for p in _merge_collinear([_piece(d) for d in dets if d.dtype == dtype], band_mm, lambda m, q: 0.0)]
    if roots:
        if spec.is_pipe:
            limit_iii = cfg.pipe_root_length_limit_iii_mm
            if limit_iii is None:
                limit_iii = std.pipe_root_length_limit_mm(spec)
            total = sum(p.length_mm for p in roots)
            root_g = std.pipe_root_grade(total, limit_iii)
            if cfg.pipe_root_strict_table26 and not spec.is_small_pipe and root_g != 4:
                root_g = max(std.pipe_root_grade_table26([p.a for p in roots if p.roi == roi], t, limit_iii)
                             for roi in {p.roi for p in roots})
            grades.append(root_g)
        elif cfg.plate_root_defects == "drop":
            warnings.append(f"承压设备本体焊缝（第 6 章）检出根部内凹/咬边 {len(roots)} 处，按配置不填报")
            roots = []
            root_g = None
        else:
            root_g = None
            warnings.append("承压设备本体焊缝（第 6 章）不对根部内凹/咬边分级，仅记录")
        for p in roots:
            records.append(make_record(p.dtype, p.members, _fmt_mm(p.length_mm), root_g, length=p.length_mm))

    records.sort(key=lambda r: (r.x_px, r.defect_type))
    grade = max(grades) if grades else 1
    return ImageEvaluation(
        image_path=str(result.get("image_path", "")), spec=spec.raw or str(spec.thickness),
        grade=grade, grade_label=std.grade_label(grade), records=records, warnings=warnings,
    )


def evaluate_results(payload: Union[Mapping[str, Any], Sequence[Mapping[str, Any]]],
                     specs: Mapping[str, Union[std.WeldSpec, str, int, float]],
                     config: Optional[EvalConfig] = None) -> List[ImageEvaluation]:
    """批量评定。payload 为 inference_results.json 内容（或其 results 列表）；specs 以文件名或去扩展名的编号为键。"""
    results = payload.get("results", []) if isinstance(payload, Mapping) else payload
    out: List[ImageEvaluation] = []
    for result in results:
        path = Path(str(result.get("image_path", "")))
        spec = specs.get(path.name, specs.get(path.stem))
        if spec is None:
            raise KeyError(f"影像信息表中找不到 {path.name} 的规格")
        out.append(evaluate_image(result, spec, config))
    return out
