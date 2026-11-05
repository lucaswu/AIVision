"""解析竞赛/测试 Excel 答案表并提交至远洋评分系统。

接口文档：http://www.farain.com:3030/doc/AI人机大赛评分系统接口说明.html
提交地址：POST http://www.farain.com:3030/testing/ai/ray/submit
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .xlsx import read_xlsx

logger = logging.getLogger(__name__)

# 缺陷列字母到 (Idx, 名称) 的映射（根据官方题目表头 A~I）
DEFECT_LETTER_MAP: Dict[str, Tuple[int, str]] = {
    "A": (1, "裂纹"),
    "B": (2, "未熔合"),
    "C": (3, "未焊透"),
    "D": (4, "条形缺陷"),
    "E": (5, "圆形缺陷"),
    "F": (6, "咬边"),
    "G": (7, "内凹"),
    "H": (8, "伪缺陷"),
    "I": (9, "综合评级"),
}

# 焊缝形式枚举
WELD_FORM_MAP: Dict[str, int] = {
    "双": 1,      # 双面焊
    "双面焊": 1,
    "单": 2,      # 单面焊
    "单面焊": 2,
    "垫单": 3,    # 垫板单面焊
    "垫板单面焊": 3,
}

# 焊接方法枚举
WELD_METHOD_MAP: Dict[str, int] = {
    "手": 1,
    "手工焊": 1,
    "埋": 2,
    "埋弧焊": 2,
    "氩": 3,
    "氩弧焊": 3,
    "手氩": 4,
    "手工焊+氩弧焊": 4,
    "埋氩": 5,
    "埋弧焊+氩弧焊": 5,
    "电渣": 6,
    "电渣焊": 6,
    "等离子": 7,
    "等离子焊": 7,
    "气保": 8,
    "二氧化碳气体保护焊": 8,
    "手埋": 9,
    "手工焊+埋弧焊": 9,
}

# 施焊位置枚举
WELD_POS_MAP: Dict[str, int] = {
    "平": 1,
    "平焊": 1,
    "立": 2,
    "立焊": 2,
    "横": 3,
    "横焊": 3,
    "仰": 4,
    "仰焊": 4,
    "全": 5,
    "全位置": 5,
}

# 评级映射
PINGJI_MAP: Dict[str, int] = {
    "I": 1, "Ⅰ": 1, "1": 1,
    "II": 2, "Ⅱ": 2, "2": 2,
    "III": 3, "Ⅲ": 3, "3": 3,
    "IV": 4, "Ⅳ": 4, "4": 4,
}


def parse_answer_excel(excel_path: Union[str, Path], is_man_machine: bool = False) -> List[Dict[str, Any]]:
    """读取并解析 10张答案.xlsx 格式的数据表。
    is_man_machine 为 False（默认）表示缺陷识别赛项，工艺三属性强制填 -1；True 则解析工艺三属性。"""
    rows = read_xlsx(excel_path)
    if len(rows) < 3:
        raise ValueError(f"Excel 行数不足（至少需要表头和数据行）: {len(rows)}")

    # 第一行通常为一级表头，第二行为二级表头
    row1 = [c.strip() for c in rows[0]]
    row2 = [c.strip() for c in rows[1]]

    # 动态定位关键列位置
    xuhao_col = 0
    pingji_col = len(row1) - 1

    # 寻找评级列
    for col_idx, (h1, h2) in enumerate(zip(row1, row2)):
        if "序号" in h1:
            xuhao_col = col_idx
        if "评级" in h1 or "评级" in h2:
            pingji_col = col_idx

    # 建立各列对应的枚举与缺陷映射
    # 查找缺陷列（row2 中的 A, B, C, D, E, F, G, H, I）
    defect_cols: Dict[int, Tuple[int, str]] = {}
    weld_form_cols: Dict[int, int] = {}
    weld_method_cols: Dict[int, int] = {}
    weld_pos_cols: Dict[int, int] = {}

    for c_idx, val in enumerate(row2):
        if val in DEFECT_LETTER_MAP:
            defect_cols[c_idx] = DEFECT_LETTER_MAP[val]
        if val in WELD_FORM_MAP:
            weld_form_cols[c_idx] = WELD_FORM_MAP[val]
        if val in WELD_METHOD_MAP:
            weld_method_cols[c_idx] = WELD_METHOD_MAP[val]
        if val in WELD_POS_MAP:
            weld_pos_cols[c_idx] = WELD_POS_MAP[val]

    submit_list: List[Dict[str, Any]] = []

    # 从第 3 行开始解析数据（索引 2）
    for r_idx in range(2, len(rows)):
        row = rows[r_idx]
        if not row:
            continue
        xuhao = row[xuhao_col].strip() if xuhao_col < len(row) else ""
        if not xuhao or not xuhao.isdigit():
            # 遇到空行或备注行时跳过
            continue

        # 焊缝形式、焊接方法、施焊位置（仅人机大战赛项解析，缺陷识别赛项强制填 -1）
        form_idx = -1
        method_idx = -1
        pos_idx = -1
        if is_man_machine:
            for c_idx, f_val in weld_form_cols.items():
                if c_idx < len(row) and "√" in row[c_idx]:
                    form_idx = f_val
                    break
            for c_idx, m_val in weld_method_cols.items():
                if c_idx < len(row) and "√" in row[c_idx]:
                    method_idx = m_val
                    break
            for c_idx, p_val in weld_pos_cols.items():
                if c_idx < len(row) and "√" in row[c_idx]:
                    pos_idx = p_val
                    break

        # 评级
        raw_pj = row[pingji_col].strip() if pingji_col < len(row) else ""
        pingji_idx = PINGJI_MAP.get(raw_pj.upper(), -1)

        # 缺陷列表
        list_defect: List[Dict[str, Any]] = []
        for c_idx, (d_idx, d_name) in defect_cols.items():
            if c_idx >= len(row):
                continue
            cell_val = row[c_idx].strip()
            if not cell_val:
                continue

            # 拆分坐标与参数，例如 '212，36'、'128，3'、'0，67'
            clean_val = cell_val.replace("，", ",").replace(" ", "")
            parts = clean_val.split(",")
            x_val = float(parts[0])
            x_str = f"{x_val:.2f}"

            if d_idx == 5:
                # 圆形缺陷：点数
                param_str = str(int(float(parts[1])))
            elif d_idx == 9:
                # 综合评级：条形长度,圆形点数
                param_str = f"{float(parts[1]):.2f},{int(float(parts[2]))}"
            elif d_idx in (8, 10, 11, 12, 13, 14):
                param_str = ""
            else:
                # 长度（整数则保留原整数或一位小数，服务端两者均兼容）
                param_val = float(parts[1])
                param_str = str(int(param_val)) if param_val.is_integer() else str(param_val)

            list_defect.append({
                "Idx": d_idx,
                "XZuoBiao": x_str,
                "CanShu": param_str,
            })

        submit_list.append({
            "TiMuXuHao": xuhao,
            "PingJiIdx": pingji_idx,
            "HanFengXingShiIdx": form_idx,
            "HanJieFangFaIdx": method_idx,
            "ShiHanWeiZhiIdx": pos_idx,
            "Type": 0,
            "ListDefect": list_defect,
        })

    return submit_list


def submit_payload(name: str,
                   password: str,
                   changci: str,
                   submit_list: List[Dict[str, Any]],
                   url: str = "http://www.farain.com:3030/testing/ai/ray/submit") -> Dict[str, Any]:
    """组装 Payload 并提交至评分服务器。"""
    payload = {
        "name": name.strip(),
        "password": password.strip(),
        "changci": changci.strip(),
        "type": 4,
        "submitList": submit_list,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_text = resp.read().decode("utf-8")
        return json.loads(res_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="解析竞赛 Excel 答案表并提交至远洋评分系统")
    parser.add_argument("--excel", required=True, help="答案 Excel 文件路径")
    parser.add_argument("--name", default="13858120789", help="学员姓名")
    parser.add_argument("--password", default="13858120789", help="考核号")
    parser.add_argument("--changci", default="122", help="场次号")
    parser.add_argument("--url", default="http://www.farain.com:3030/testing/ai/ray/submit", help="评分接口地址")
    parser.add_argument("--man-machine", action="store_true", help="指定为人机大战赛项（解析工艺三属性；未指定则默认缺陷识别，强制填 -1）")
    args = parser.parse_args()

    items = parse_answer_excel(args.excel, is_man_machine=args.man_machine)
    print(f"解析完成，共 {len(items)} 道题，正在提交至 {args.url} ...")
    resp = submit_payload(args.name, args.password, args.changci, items, url=args.url)
    print(f"服务器返回结果: {resp}")


