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
                           pos_override: Optional[Union[str, int]] = None) -> CraftAttributes:
    """根据工件规格（管件/板厚/垫板模式）与焊接工程先验自动推断工艺三属性。

    支持手动覆盖（传入枚举 int 或中文 string）。
    """
    s = spec if isinstance(spec, WeldSpec) else parse_spec(spec)

    # 1. 焊缝形式 (HanFengXingShiIdx: 1双面, 2单面, 3垫板单面)
    if form_override is not None:
        form_idx = form_override if isinstance(form_override, int) else WELD_FORM_MAP.get(str(form_override).strip(), -1)
    elif s.extra_thickness is not None and s.extra_thickness > 0:
        # 如 "20+4" 显式带垫板或复合层
        form_idx = 3  # 垫板单面焊
    elif s.is_pipe:
        # 管道对接环缝工程上通常为不加垫板单面焊 (小径管/中径管)
        form_idx = 2  # 单面焊
    else:
        # 承压设备本体板焊缝通常为开坡口双面焊
        form_idx = 1  # 双面焊

    # 2. 施焊位置 (ShiHanWeiZhiIdx: 1平, 2立, 3横, 4仰, 5全位置)
    if pos_override is not None:
        pos_idx = pos_override if isinstance(pos_override, int) else WELD_POSITION_MAP.get(str(pos_override).strip(), -1)
    elif s.is_pipe:
        # 管道固定口环焊通常为全位置焊
        pos_idx = 5  # 全位置
    else:
        # 板类及容器筒体工厂制造通常处于平焊（转胎或平焊位）
        pos_idx = 1  # 平焊

    # 3. 焊接方法 (HanJieFangFaIdx: 1手工, 2埋弧, 3氩弧, 4手工+氩, 5埋弧+氩, 8二保, 9手工+埋弧)
    if method_override is not None:
        method_idx = method_override if isinstance(method_override, int) else WELD_METHOD_MAP.get(str(method_override).strip(), -1)
    elif s.is_pipe:
        if s.is_small_pipe or s.thickness <= 6.0:
            # 小径管/薄壁管打底和盖面普遍采用全氩弧焊
            method_idx = 3  # 氩弧焊
        else:
            # 中大径管道一般为氩弧焊打底 + 手工焊/气体保护焊填充盖面
            method_idx = 4  # 手工焊+氩弧焊
    else:
        # 板焊缝：
        if s.thickness >= 25.0:
            # 大厚板主体焊接普遍采用埋弧自动焊
            method_idx = 2  # 埋弧焊
        elif s.thickness >= 12.0:
            # 中厚板常采用手工电弧焊打底 + 埋弧焊盖面
            method_idx = 9  # 手工焊+埋弧焊
        else:
            # 较薄板多为手工焊
            method_idx = 1  # 手工焊

    return CraftAttributes(
        weld_form_idx=form_idx,
        welding_method_idx=method_idx,
        welding_position_idx=pos_idx,
    )

