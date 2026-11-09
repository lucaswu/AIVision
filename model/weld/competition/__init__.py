"""2026 全国无损检测射线 AI 智能评片大赛：缺陷定位 / 定性 / 定量 / NB/T 47013.2-2015 评级。

纯规则计算，不依赖模型与 OpenCV；输入为推理结果（inference_results.json 中的单图 result）
与《影像信息表》中的规格，输出可直接用于填报的缺陷记录与整图评定等级。
"""

from .client import (
    DEFECT_IDX_TO_NAME,
    DEFECT_TYPE_TO_IDX,
    SubmitResponse,
    build_submission_payload,
    build_submit_item,
    calibrate_defect_records,
    save_submission_json,
    select_primary_defects,
    submit_to_server,
    validate_submission_payload,
)
from .evaluator import DefectRecord, EvalConfig, ImageEvaluation, evaluate_image, evaluate_results
from .process_infer import CraftAttributes, infer_craft_attributes
from .standards import WeldSpec, parse_spec

__all__ = [
    "CraftAttributes",
    "DEFECT_IDX_TO_NAME",
    "DEFECT_TYPE_TO_IDX",
    "DefectRecord",
    "EvalConfig",
    "ImageEvaluation",
    "SubmitResponse",
    "WeldSpec",
    "build_submission_payload",
    "build_submit_item",
    "calibrate_defect_records",
    "evaluate_image",
    "evaluate_results",
    "infer_craft_attributes",
    "parse_spec",
    "save_submission_json",
    "select_primary_defects",
    "submit_to_server",
    "validate_submission_payload",
]
