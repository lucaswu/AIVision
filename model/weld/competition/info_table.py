"""《影像信息表》读取：影像序号 / 影像名称 / 规格 / 材质。

支持 .xlsx（标准库解析）、.xls（需 xlrd）、.csv，以及旧的逐图规格 JSON（{"1.dcm": "28"}）。
表头按列名定位（允许前面有标题行），找不到表头时按“序号、名称、规格、材质”列顺序读取。
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from .standards import parse_spec
from .xlsx import read_xlsx

_HEADER_KEYS = {
    "index": ("影像序号", "序号", "编号"),
    "name": ("影像名称", "名称", "文件名", "影像"),
    "spec": ("规格",),
    "material": ("材质", "材料"),
}


@dataclass(frozen=True)
class InfoRow:
    index: Optional[int]
    name: str        # 如 "1.dcm"；表中只有序号时补成 "<序号>"
    spec: str
    material: str = ""

    @property
    def stem(self) -> str:
        return Path(self.name).stem


def _read_rows(path: Path) -> List[List[str]]:
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if ext == ".xls":
        try:
            import xlrd  # type: ignore
        except ImportError as exc:
            raise ValueError("读取 .xls 需要 xlrd；或在 Excel 中另存为 .xlsx") from exc
        sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)
        rows = []
        for r in range(sheet.nrows):
            row = []
            for v in sheet.row_values(r):
                row.append(str(int(v)) if isinstance(v, float) and v.is_integer() else str(v))
            rows.append(row)
        return rows
    if ext in (".csv", ".txt"):
        raw = path.read_bytes()
        for enc in ("utf-8-sig", "gbk"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("CSV 编码无法识别（需 UTF-8 或 GBK）")
        return [list(r) for r in csv.reader(text.splitlines())]
    raise ValueError(f"不支持的影像信息表格式: {ext}")


def _find_header(rows: Sequence[Sequence[str]]):
    for r_idx, row in enumerate(rows[:20]):
        cols: Dict[str, int] = {}
        for c_idx, cell in enumerate(row):
            text = re.sub(r"\s+", "", str(cell))
            for key, names in _HEADER_KEYS.items():
                if key not in cols and any(text == n or text.startswith(n) for n in names):
                    cols[key] = c_idx
                    break
        if "spec" in cols and ("name" in cols or "index" in cols):
            return r_idx, cols
    return -1, {"index": 0, "name": 1, "spec": 2, "material": 3}


def _to_int(text: str) -> Optional[int]:
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def load_info_table(path: Union[str, Path]) -> List[InfoRow]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON 需为 {文件名或编号: 规格} 对象")
        return [InfoRow(_to_int(Path(str(k)).stem), str(k), str(v)) for k, v in data.items()]

    rows = _read_rows(path)
    header_row, cols = _find_header(rows)
    out: List[InfoRow] = []
    for row in rows[header_row + 1:]:
        get = lambda key: str(row[cols[key]]).strip() if key in cols and cols[key] < len(row) else ""  # noqa: E731
        spec, name, index = get("spec"), get("name"), _to_int(get("index"))
        if not spec or (not name and index is None):
            continue
        if not name:
            name = str(index)
        out.append(InfoRow(index, name, spec, get("material")))
    if not out:
        raise ValueError("影像信息表中没有读到任何“影像名称 + 规格”行")
    return out


def spec_map(rows: Sequence[InfoRow]) -> Dict[str, str]:
    """{文件名 / 去扩展名编号 / 序号: 规格}，供 RunConfig.competition_specs 使用。"""
    out: Dict[str, str] = {}
    for r in rows:
        out[r.name] = r.spec
        out.setdefault(r.stem, r.spec)
        if r.index is not None:
            out.setdefault(str(r.index), r.spec)
    return out


def validate(rows: Sequence[InfoRow]) -> List[str]:
    """返回无法解析的规格描述（为空表示全部可用）。"""
    bad = []
    for r in rows:
        try:
            parse_spec(r.spec)
        except ValueError:
            bad.append(f"{r.name}: {r.spec}")
    return bad
