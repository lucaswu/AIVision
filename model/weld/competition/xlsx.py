"""极简 .xlsx 读写（仅标准库）。

比赛现场机器不保证装有 openpyxl，《影像信息表》读取与答案导出都只需要“第一张表的单元格文本”，
这里直接解析/生成 OOXML。只支持值，不处理样式、公式求值（读取公式单元格的缓存值）。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
_CELL_RE = re.compile(r"([A-Z]+)(\d+)")


def _col_index(ref: str) -> int:
    m = _CELL_RE.match(ref)
    letters = m.group(1) if m else "A"
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def _col_letter(idx: int) -> str:
    out = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def _text(node) -> str:
    """<si>/<is> 下所有 <t> 拼接（含富文本 run）。"""
    return "".join(t.text or "" for t in node.iter(f"{{{_NS['m']}}}t"))


def _first_sheet_path(zf: zipfile.ZipFile) -> str:
    try:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        sheet = wb.find("m:sheets/m:sheet", _NS)
        rid = sheet.get(f"{{{_NS['r']}}}id") if sheet is not None else None
        for rel in rels.findall("rel:Relationship", _NS):
            if rel.get("Id") == rid:
                target = rel.get("Target", "").lstrip("/")
                return target if target.startswith("xl/") else f"xl/{target}"
    except KeyError:
        pass
    return "xl/worksheets/sheet1.xml"


def read_xlsx(path: Union[str, Path]) -> List[List[str]]:
    """返回第一张工作表的二维文本（行 × 列，空单元格为 ""）。"""
    with zipfile.ZipFile(path) as zf:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root.findall("m:si", _NS)]
        sheet = ET.fromstring(zf.read(_first_sheet_path(zf)))

    rows: List[List[str]] = []
    for row in sheet.iter(f"{{{_NS['m']}}}row"):
        values: Dict[int, str] = {}
        for pos, c in enumerate(row.findall("m:c", _NS)):
            ref = c.get("r")
            col = _col_index(ref) if ref else pos
            ctype = c.get("t", "n")
            if ctype == "inlineStr":
                is_node = c.find("m:is", _NS)
                values[col] = _text(is_node) if is_node is not None else ""
                continue
            v = c.find("m:v", _NS)
            raw = v.text if v is not None and v.text is not None else ""
            if ctype == "s" and raw:
                values[col] = shared[int(raw)]
            elif ctype == "n" and raw:
                num = float(raw)
                values[col] = str(int(num)) if num.is_integer() else raw
            else:
                values[col] = raw
        r_idx = int(row.get("r", len(rows) + 1)) - 1
        while len(rows) < r_idx:
            rows.append([])
        width = max(values) + 1 if values else 0
        rows.append([values.get(i, "") for i in range(width)])
    return rows


def write_xlsx(path: Union[str, Path], rows: Sequence[Sequence[Any]], sheet_name: str = "Sheet1") -> None:
    """写单表 .xlsx；数字写为数值单元格，其余写内联字符串。"""
    lines = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{_col_letter(c)}{r}"
            if value is None or value == "":
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
        lines.append(f'<row r="{r}">{"".join(cells)}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<worksheet xmlns="{_NS["m"]}"><sheetData>{"".join(lines)}</sheetData></worksheet>')
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_NS["rel"]}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{_NS["m"]}" xmlns:r="{_NS["r"]}"><sheets>'
            f'<sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_NS["rel"]}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'worksheet" Target="worksheets/sheet1.xml"/></Relationships>'),
        "xl/worksheets/sheet1.xml": sheet,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
