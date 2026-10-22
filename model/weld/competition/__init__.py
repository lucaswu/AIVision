"""2026 全国无损检测射线 AI 智能评片大赛：缺陷定位 / 定性 / 定量 / NB/T 47013.2-2015 评级。

纯规则计算，不依赖模型与 OpenCV；输入为推理结果（inference_results.json 中的单图 result）
与《影像信息表》中的规格，输出可直接用于填报的缺陷记录与整图评定等级。
"""

from .evaluator import DefectRecord, EvalConfig, ImageEvaluation, evaluate_image, evaluate_results
from .standards import WeldSpec, parse_spec

__all__ = [
    "DefectRecord",
    "EvalConfig",
    "ImageEvaluation",
    "WeldSpec",
    "evaluate_image",
    "evaluate_results",
    "parse_spec",
]
