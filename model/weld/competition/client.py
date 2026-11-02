"""远洋 AI 人机大赛评分系统接口客户端与提交 Payload 构建器。

接口说明文档：http://www.farain.com:3030/doc/AI人机大赛评分系统接口说明.html
提交地址：POST http://www.farain.com:3030/testing/ai/ray/submit
请求头：Content-Type: application/json
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .evaluator import DefectRecord, ImageEvaluation
from .process_infer import CraftAttributes, infer_craft_attributes
from .standards import WeldSpec, parse_spec

DEFAULT_SUBMIT_URL = "http://www.farain.com:3030/testing/ai/ray/submit"

logger = logging.getLogger(__name__)

# 服务端缺陷枚举 (EDefect)
DEFECT_TYPE_TO_IDX: Dict[str, int] = {
    "裂纹": 1,
    "未熔合": 2,
    "未焊透": 3,
    "条形缺陷": 4,
    "圆形缺陷": 5,
    "咬边": 6,
    "根部咬边": 6,
    "内凹": 7,
    "根部内凹": 7,
    "伪缺陷": 8,
    "综合评级": 9,
    "烧穿": 10,
    "错边": 11,
    "偏析": 12,
    "衍射": 13,
    "未填满": 14,
}

DEFECT_IDX_TO_NAME: Dict[int, str] = {
    1: "裂纹",
    2: "未熔合",
    3: "未焊透",
    4: "条形缺陷",
    5: "圆形缺陷",
    6: "咬边",
    7: "内凹",
    8: "伪缺陷",
    9: "综合评级",
    10: "烧穿",
    11: "错边",
    12: "偏析",
    13: "衍射",
    14: "未填满",
    0: " ",
}


# ---------------------------------------------------------------------------
# 单题与缺陷项构建
# ---------------------------------------------------------------------------

def format_x_coordinate(x_mm: Union[float, int, str]) -> str:
    """X 坐标写成数字字符串，保留两位小数，例如 '12.50'。"""
    try:
        val = float(x_mm)
        return f"{val:.2f}"
    except (ValueError, TypeError):
        return str(x_mm)


def format_defect_parameter(idx: int, rec: Mapping[str, Any]) -> str:
    """按缺陷类型格式化 CanShu 字符串：
    - 圆形缺陷 (Idx 5)：点数字符串，例如 '3'
    - 综合评级 (Idx 9)：'条形长度,圆形点数'，例如 '12.50,3'（长度保留 2 位小数）
    - 伪缺陷/烧穿/错边/偏析/衍射/未填满：留空 ''
    - 其余缺陷 (1, 2, 3, 4, 6, 7)：长度字符串，保留 2 位小数，例如 '12.50'
    """
    if idx == 5:
        # 圆形缺陷：点数
        pts = rec.get("points")
        if pts is not None:
            return str(int(pts))
        qty = str(rec.get("quantity", "")).strip()
        return qty if qty.isdigit() else "0"

    if idx == 9:
        # 综合评级：条形缺陷长度,圆形缺陷点数
        strip_len = rec.get("length_mm")
        pts = rec.get("points")
        if strip_len is not None and pts is not None:
            return f"{float(strip_len):.2f},{int(pts)}"
        # 若未直接提供，尝试解析 quantity (如 "12.5, 3")
        qty = str(rec.get("quantity", "")).replace("，", ",")
        parts = [p.strip() for p in qty.split(",") if p.strip()]
        if len(parts) >= 2:
            try:
                l_val = float(parts[0])
                p_val = int(parts[1])
                return f"{l_val:.2f},{p_val}"
            except ValueError:
                return f"{parts[0]},{parts[1]}"
        return qty

    if idx in (8, 10, 11, 12, 13, 14):
        # 无需长度参数
        return ""

    # 线性/面状缺陷：长度
    length = rec.get("length_mm")
    if length is not None:
        return f"{float(length):.2f}"
    qty = str(rec.get("quantity", "")).strip()
    try:
        val = float(qty)
        return f"{val:.2f}"
    except ValueError:
        return qty


def build_defect_item(rec: Union[DefectRecord, Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """将单条缺陷记录转换为服务端 ListDefect 项。"""
    r = rec if isinstance(rec, Mapping) else rec.__dict__
    dtype = str(r.get("defect_type", "")).strip()
    if not dtype or dtype in ("无", "无缺陷", "none", "null"):
        return None

    idx = DEFECT_TYPE_TO_IDX.get(dtype)
    if idx is None:
        logger.warning(f"未知缺陷定性已忽略: {dtype}")
        return None

    x_val = r.get("x_mm")
    if x_val is None:
        x_val = r.get("x_px", 0.0)
    x_str = format_x_coordinate(x_val)
    param_str = format_defect_parameter(idx, r)

    return {
        "Idx": idx,
        "XZuoBiao": x_str,
        "CanShu": param_str,
    }


def build_submit_item(ev: Union[ImageEvaluation, Mapping[str, Any]],
                      spec: Optional[Union[WeldSpec, str, int, float]] = None,
                      craft: Optional[CraftAttributes] = None) -> Dict[str, Any]:
    """构建 submitList 中的单题对象。"""
    d = ev if isinstance(ev, Mapping) else ev.to_dict()
    img_name = str(d.get("image_name", ""))
    # TiMuXuHao：题库真实序号，字符串，与图片文件名（去掉扩展名）一一对应
    timu_xuhao = Path(img_name).stem if img_name else str(d.get("image_path", ""))

    # PingJiIdx：取「评级 PingJi」的 value (1..4)，未选择填 -1
    raw_grade = d.get("grade", -1)
    pingji_idx = int(raw_grade) if raw_grade in (1, 2, 3, 4) else -1

    # 工艺属性推断
    if craft is None:
        spec_val = spec or d.get("spec", "")
        craft = infer_craft_attributes(spec_val) if spec_val else CraftAttributes()

    # ListDefect 构建：没有缺陷时传空数组 []
    defect_list: List[Dict[str, Any]] = []
    records = d.get("records") or []
    for rec in records:
        item = build_defect_item(rec)
        if item is not None:
            defect_list.append(item)

    return {
        "TiMuXuHao": timu_xuhao,
        "PingJiIdx": pingji_idx,
        "HanFengXingShiIdx": craft.weld_form_idx,
        "HanJieFangFaIdx": craft.welding_method_idx,
        "ShiHanWeiZhiIdx": craft.welding_position_idx,
        "Type": 0,
        "ListDefect": defect_list,
    }


# ---------------------------------------------------------------------------
# 全局 Payload 构建与校验
# ---------------------------------------------------------------------------

def build_submission_payload(name: str,
                             password: str,
                             changci: str,
                             items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """构建顶层 POST 请求体。"""
    return {
        "name": str(name).strip(),
        "password": str(password).strip(),
        "changci": str(changci).strip(),
        "type": 4,  # 固定填 4
        "submitList": list(items),
    }


def validate_submission_payload(payload: Mapping[str, Any]) -> List[str]:
    """对即将提交的 payload 执行全面合规自检，返回问题描述列表（为空表示完全合规）。"""
    issues: List[str] = []
    for f in ("name", "password", "changci"):
        if not str(payload.get(f, "")).strip():
            issues.append(f"顶层必填字段缺失或为空: '{f}'")

    if payload.get("type") != 4:
        issues.append(f"type 必须固定为 4，当前值为: {payload.get('type')}")

    submit_list = payload.get("submitList")
    if not isinstance(submit_list, list):
        issues.append("submitList 必须是 JSON 数组")
        return issues

    if len(submit_list) == 0:
        issues.append("submitList 题库数组为空")

    for idx, item in enumerate(submit_list):
        if not isinstance(item, dict):
            issues.append(f"第 {idx} 题数据不是 JSON 对象")
            continue
        xuhao = str(item.get("TiMuXuHao", "")).strip()
        if not xuhao:
            issues.append(f"第 {idx} 题缺失 TiMuXuHao")
        if item.get("Type") != 0:
            issues.append(f"第 {idx} 题 ({xuhao}) Type 必须固定为 0")
        if item.get("PingJiIdx") not in (1, 2, 3, 4, -1):
            issues.append(f"第 {idx} 题 ({xuhao}) PingJiIdx 值非法: {item.get('PingJiIdx')}")

        defects = item.get("ListDefect")
        if not isinstance(defects, list):
            issues.append(f"第 {idx} 题 ({xuhao}) ListDefect 必须为数组")
            continue

        for d_idx, defect in enumerate(defects):
            d_type_idx = defect.get("Idx")
            if d_type_idx not in DEFECT_IDX_TO_NAME:
                issues.append(f"第 {idx} 题 ({xuhao}) 第 {d_idx} 条缺陷 Idx 非法: {d_type_idx}")
            x_str = str(defect.get("XZuoBiao", ""))
            # 校验 X 坐标两位小数格式
            if d_type_idx not in (8, 10, 11, 12, 13, 14, 0, -1):
                if not re.fullmatch(r"-?\d+(\.\d{2})?", x_str):
                    issues.append(f"第 {idx} 题 ({xuhao}) 缺陷 X 坐标格式不合规（需保留两位小数）: {x_str!r}")
            # 综合评级参数校验
            if d_type_idx == 9:
                param = str(defect.get("CanShu", ""))
                if not re.fullmatch(r"\d+(\.\d{2})?,\d+", param):
                    issues.append(f"第 {idx} 题 ({xuhao}) 综合评级参数需为 '长度,点数' (如 12.50,3): {param!r}")

    return issues


def save_submission_json(payload: Mapping[str, Any], path: Union[str, Path]) -> Path:
    """将完整请求体保存为标准 JSON 文件，用于 U 盘应急离线拷贝。"""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return out_path


# ---------------------------------------------------------------------------
# 在线网络提交
# ---------------------------------------------------------------------------

@dataclass
class SubmitResponse:
    success: bool
    code: int
    data: Dict[str, Any]
    error_msg: str
    raw_text: str


def submit_to_server(payload: Mapping[str, Any],
                     url: str = DEFAULT_SUBMIT_URL,
                     timeout: float = 20.0) -> SubmitResponse:
    """执行 HTTP POST 提交至评分系统接口。"""
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "AIVision-Competition-Client/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_text = resp.read().decode("utf-8", errors="replace")
            status_code = resp.status
    except urllib.error.HTTPError as http_err:
        raw_text = http_err.read().decode("utf-8", errors="replace")
        return SubmitResponse(
            success=False,
            code=http_err.code,
            data={},
            error_msg=f"HTTP 错误 {http_err.code}: {raw_text}",
            raw_text=raw_text,
        )
    except urllib.error.URLError as net_err:
        return SubmitResponse(
            success=False,
            code=-1,
            data={},
            error_msg=f"网络连接失败: {net_err.reason}",
            raw_text="",
        )
    except Exception as exc:
        return SubmitResponse(
            success=False,
            code=-2,
            data={},
            error_msg=f"请求异常: {exc}",
            raw_text="",
        )

    try:
        res_json = json.loads(raw_text)
    except json.JSONDecodeError:
        return SubmitResponse(
            success=False,
            code=-3,
            data={},
            error_msg=f"服务端返回非合法 JSON: {raw_text[:200]}",
            raw_text=raw_text,
        )

    code = res_json.get("code", -9999)
    err_msg = res_json.get("errMsg", "")
    data = res_json.get("data") or {}

    return SubmitResponse(
        success=(code == 0),
        code=code,
        data=data,
        error_msg=err_msg,
        raw_text=raw_text,
    )

