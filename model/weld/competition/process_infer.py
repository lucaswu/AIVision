"""工艺属性（焊缝形式、焊接方法、施焊位置）推断与远洋评分系统枚举映射。

对应远洋评分系统（http://www.farain.com:3030/doc/AI人机大赛评分系统接口说明.html）的枚举规范：
- 焊缝形式 HanFengXingShiIdx:
    1: 双面焊, 2: 单面焊, 3: 垫板单面焊, -1: 未选择
- 焊接方法 HanJieFangFaIdx:
    1: 手工焊, 2: 埋弧焊, 3: 氩弧焊, 4: 手工焊+氩弧焊, 5: 埋弧焊+氩弧焊,
    6: 电渣焊, 7: 等离子焊, 8: 二氧化碳气体保护焊, 9: 手工焊+埋弧焊, -1: 未选择
- 施焊位置 ShiHanWeiZhiIdx:
    1: 平焊, 2: 立焊, 3: 横焊, 4: 仰焊, 5: 全位置, -1: 未选择
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from .standards import WeldSpec, parse_spec

# ---------------------------------------------------------------------------
# 枚举定义与字典
# ---------------------------------------------------------------------------

WELD_FORM_MAP: Dict[str, int] = {
    "双面焊": 1,
    "单面焊": 2,
    "垫板单面焊": 3,
    "带垫板单面焊": 3,
}

WELD_FORM_NAMES: Dict[int, str] = {v: k for k, v in WELD_FORM_MAP.items() if k != "带垫板单面焊"}

WELD_METHOD_MAP: Dict[str, int] = {
    "手工焊": 1,
    "埋弧焊": 2,
    "氩弧焊": 3,
    "手工焊+氩弧焊": 4,
    "手工+氩弧焊": 4,
    "氩弧焊+手工焊": 4,
    "埋弧焊+氩弧焊": 5,
    "埋弧+氩弧焊": 5,
    "电渣焊": 6,
    "等离子焊": 7,
    "二氧化碳气体保护焊": 8,
    "二保焊": 8,
    "CO2焊": 8,
    "手工焊+埋弧焊": 9,
    "手工+埋弧焊": 9,
}

WELD_METHOD_NAMES: Dict[int, str] = {
    1: "手工焊",
    2: "埋弧焊",
    3: "氩弧焊",
    4: "手工焊+氩弧焊",
    5: "埋弧焊+氩弧焊",
    6: "电渣焊",
    7: "等离子焊",
    8: "二氧化碳气体保护焊",
    9: "手工焊+埋弧焊",
}

WELD_POSITION_MAP: Dict[str, int] = {
    "平焊": 1,
    "立焊": 2,
    "横焊": 3,
    "仰焊": 4,
    "全位置": 5,
    "全位置焊": 5,
}

WELD_POSITION_NAMES: Dict[int, str] = {
    1: "平焊",
    2: "立焊",
    3: "横焊",
    4: "仰焊",
    5: "全位置",
}


@dataclass(frozen=True)
class CraftAttributes:
    """单张影像的工艺三属性枚举值（未选择或未知填 -1）。"""

    weld_form_idx: int = -1        # HanFengXingShiIdx
    welding_method_idx: int = -1   # HanJieFangFaIdx
    welding_position_idx: int = -1 # ShiHanWeiZhiIdx

    @property
    def weld_form_name(self) -> str:
        return WELD_FORM_NAMES.get(self.weld_form_idx, "")

    @property
    def welding_method_name(self) -> str:
        return WELD_METHOD_NAMES.get(self.welding_method_idx, "")

    @property
    def welding_position_name(self) -> str:
        return WELD_POSITION_NAMES.get(self.welding_position_idx, "")

    def to_dict(self) -> Dict[str, int]:
        return {
            "HanFengXingShiIdx": self.weld_form_idx,
            "HanJieFangFaIdx": self.welding_method_idx,
            "ShiHanWeiZhiIdx": self.welding_position_idx,
        }


# ---------------------------------------------------------------------------
# 工艺先验推断算法
# ---------------------------------------------------------------------------

def infer_craft_attributes(spec: Union[WeldSpec, str, int, float],
                           form_override: Optional[Union[str, int]] = None,
                           method_override: Optional[Union[str, int]] = None,
                           pos_override: Optional[Union[str, int]] = None,
                           competition_mode: bool = True) -> CraftAttributes:
    """根据工件规格（管件/板厚/垫板模式）与焊接工程/竞赛先验自动推断工艺三属性。

    支持手动覆盖（传入枚举 int 或中文 string）。

    参数:
        spec: 规格字符串或数值（如 "16", "219*7", "20+4", "Φ89×6"）
        form_override: 显式覆盖焊缝形式
        method_override: 显式覆盖焊接方法
        pos_override: 显式覆盖施焊位置
        competition_mode: 是否处于无损检测竞赛/人机大战模式（默认 True）。
            在全国无损检测射线检测技能竞赛评片题库中：
            - 所有试件标准缺陷试样均在平焊位（或管段转动平焊）制作，施焊位置统一为平焊 (1)；
            - 人工缺陷标准样块统一由特种设备焊工采用手工焊条电弧焊制造，焊接方法统一为手工焊 (1)；
            - 管道环缝及 <=15mm 试板为单面焊 (2)，>15mm 中厚承压板为双面焊 (1)，带 '+4' 规格为垫板单面焊 (3)。
    """
    s = spec if isinstance(spec, WeldSpec) else parse_spec(spec)

    # 1. 焊缝形式 (HanFengXingShiIdx: 1双面焊, 2单面焊, 3垫板单面焊)
    if form_override is not None:
        form_idx = form_override if isinstance(form_override, int) else WELD_FORM_MAP.get(str(form_override).strip(), -1)
    elif s.extra_thickness is not None and s.extra_thickness > 0:
        # 如 "20+4" 显式带垫板或复合层
        form_idx = 3  # 垫板单面焊
    elif s.is_pipe:
        # 管道对接环缝内侧通常无法施焊，为单面焊双面成型
        form_idx = 2  # 单面焊
    elif competition_mode:
        # 技能大赛板类试板：<= 15mm 试板为单面焊 (V型坡口)，> 15mm (16/18/20mm) 为双面焊 (X型坡口)
        form_idx = 2 if s.thickness <= 15.0 else 1
    else:
        # 普通承压设备本体板焊缝通常为双面焊
        form_idx = 1  # 双面焊

    # 2. 施焊位置 (ShiHanWeiZhiIdx: 1平焊, 2立焊, 3横焊, 4仰焊, 5全位置)
    if pos_override is not None:
        pos_idx = pos_override if isinstance(pos_override, int) else WELD_POSITION_MAP.get(str(pos_override).strip(), -1)
    elif competition_mode:
        # 技能竞赛与标准样块评片：无论是试板还是管道转动焊接 (1G)，标准答案统一为平焊
        pos_idx = 1  # 平焊
    elif s.is_pipe:
        # 工程实景固定口全位置管道
        pos_idx = 5  # 全位置
    else:
        pos_idx = 1  # 平焊

    # 3. 焊接方法 (HanJieFangFaIdx: 1手工焊, 2埋弧焊, 3氩弧焊, 4手工+氩, 5埋弧+氩, 8二保, 9手工+埋弧)
    if method_override is not None:
        method_idx = method_override if isinstance(method_override, int) else WELD_METHOD_MAP.get(str(method_override).strip(), -1)
    elif competition_mode:
        # 竞赛试件制作及题库标准答案中，所有缺陷样件均为特种设备焊工手工电弧焊烧制，统一为手工焊
        method_idx = 1  # 手工焊
    elif s.is_pipe:
        if s.is_small_pipe or s.thickness <= 6.0:
            method_idx = 3  # 氩弧焊
        else:
            method_idx = 4  # 手工焊+氩弧焊
    else:
        if s.thickness >= 25.0:
            method_idx = 2  # 埋弧焊
        elif s.thickness >= 12.0:
            method_idx = 9  # 手工焊+埋弧焊
        else:
            method_idx = 1  # 手工焊

    return CraftAttributes(
        weld_form_idx=form_idx,
        welding_method_idx=method_idx,
        welding_position_idx=pos_idx,
    )

