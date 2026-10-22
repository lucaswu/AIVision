"""竞赛答案导出：competition_answers.xlsx / .csv。

每幅影像至少一行（无缺陷、推理失败、超时未完成的影像也输出），按影像序号排序；
组委会正式提交格式发布前，列结构以 ANSWER_COLUMNS 为准，调整时只改这里。
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .info_table import InfoRow
from .standards import grade_label
from .xlsx import write_xlsx

NO_DEFECT = "无缺陷"


def answer_columns() -> List[str]:
    return (["影像序号", "影像名称", "规格", "材质"]
            + ["缺陷序号", "缺陷定位X(像素)", "缺陷定位X(mm)", "缺陷定性", "缺陷定量", "评定等级", "备注"])


@dataclass
class ExportResult:
    xlsx_path: Optional[Path]
    csv_path: Path
    rows: int
    images: int
    issues: List[str] = field(default_factory=list)  # 合法性检查发现的问题（不阻止导出）


def _num_key(name: str) -> Tuple[int, Any]:
    m = re.match(r"\d+", Path(name).stem)
    return (0, int(m.group())) if m else (1, name.lower())


def _quantity_ok(dtype: str, quantity: str, sep: str) -> bool:
    if dtype == "圆形缺陷":
        return quantity.isdigit()
    if dtype == "综合评级":
        parts = quantity.split(sep.strip() or ",")
        return len(parts) == 2 and all(re.fullmatch(r"\s*\d+(\.\d+)?\s*", p) for p in parts)
    return re.fullmatch(r"\d+(\.\d+)?", quantity) is not None


def export_answers(out_dir: Path, evaluations: Sequence[Mapping[str, Any]], image_names: Sequence[str],
                   info_rows: Sequence[InfoRow] = (), failures: Optional[Mapping[str, str]] = None,
                   default_grade: int = 1, quantity_separator: str = ", ",
                   basename: str = "competition_answers") -> ExportResult:
    """evaluations 为 ImageEvaluation.to_dict()；image_names 为本次全部输入影像文件名；
    failures 为 {文件名: 原因}（推理失败/超时），这些影像按 default_grade 无缺陷兜底。"""
    failures = dict(failures or {})
    info_by_name: Dict[str, InfoRow] = {}
    for r in info_rows:
        info_by_name.setdefault(r.name.lower(), r)
        info_by_name.setdefault(r.stem.lower(), r)
        if r.index is not None:
            info_by_name.setdefault(str(r.index), r)
    ev_by_name = {str(e.get("image_name", "")).lower(): e for e in evaluations}

    names = list(dict.fromkeys(image_names))
    seen = {n.lower() for n in names}
    issues: List[str] = []
    for r in info_rows:
        if r.name.lower() not in seen and r.stem.lower() not in {Path(n).stem.lower() for n in names}:
            issues.append(f"影像信息表中的 {r.name} 不在输入影像中")

    def lookup(name: str) -> Optional[InfoRow]:
        return info_by_name.get(name.lower()) or info_by_name.get(Path(name).stem.lower())

    def order(name: str) -> Tuple[int, Any]:
        info = lookup(name)
        return (0, info.index) if info and info.index is not None else _num_key(name)

    names.sort(key=order)

    columns = answer_columns()
    rows: List[List[Any]] = []
    for name in names:
        info = lookup(name)
        ev = ev_by_name.get(name.lower())
        key = order(name)
        index = key[1] if key[0] == 0 else ""
        spec_text = (ev or {}).get("spec") or (info.spec if info else "")
        material = info.material if info else ""
        note = failures.get(name, "")
        if ev is None and not note:
            note = "未评定（缺少规格）"
            issues.append(f"{name}: {note}")

        head = [index, name, spec_text, material]
        grade_text = (ev or {}).get("grade_label") or grade_label(default_grade)
        records = (ev or {}).get("records") or []
        if not records:
            rows.append(head + ["", "", "", NO_DEFECT, "", grade_text, note])
            continue
        for i, rec in enumerate(records, start=1):
            dtype, qty = rec["defect_type"], str(rec["quantity"])
            if not _quantity_ok(dtype, qty, quantity_separator):
                issues.append(f"{name} 第 {i} 个缺陷定量格式异常: {dtype} {qty!r}")
            rows.append(head + [i, rec["x_px"], rec["x_mm"], dtype, qty, grade_text, note])

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{basename}.csv"
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    xlsx_path: Optional[Path] = out_dir / f"{basename}.xlsx"
    try:
        write_xlsx(xlsx_path, [columns] + rows, sheet_name="答案")
    except OSError as exc:
        issues.append(f"xlsx 写入失败: {exc}")
        xlsx_path = None
    return ExportResult(xlsx_path, csv_path, len(rows), len(names), issues)


def time_score(elapsed_s: float, limit_min: float = 40.0) -> float:
    """时间系数得分 B = D / 40 × 10（D 为剩余分钟；超时为 0）。"""
    remaining = limit_min - elapsed_s / 60.0
    return round(max(0.0, remaining) / limit_min * 10.0, 2)


@dataclass
class TimeForecast:
    avg_s: float          # 平均每幅推理耗时（不含模型加载）
    projected_s: float    # 按当前速度预计的总用时（含已用时间）
    score: float          # 预计时间分 B


def forecast(elapsed_s: float, infer_elapsed_s: float, done: int, total: int,
             limit_min: float = 40.0, now_elapsed_s: Optional[float] = None) -> Optional[TimeForecast]:
    """按已完成影像的平均耗时外推总用时与时间分；尚无完成影像时返回 None。

    elapsed_s / infer_elapsed_s 取“第 done 幅完成时”的总用时 / 推理用时（不含正在处理的那幅）；
    now_elapsed_s 为当前总用时，预计值不会小于它。"""
    if done <= 0:
        return None
    avg = infer_elapsed_s / done
    projected = elapsed_s + avg * max(0, total - done)
    if now_elapsed_s is not None:
        projected = max(projected, now_elapsed_s)
    return TimeForecast(avg, projected, time_score(projected, limit_min))
