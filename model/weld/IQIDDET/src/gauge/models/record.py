#!/usr/bin/env python3
"""Top-level IQI record Pydantic model."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from gauge.models.fields import GeneralFields, FieldStatistics
from gauge.models.ocr import OCRResult
from gauge.models.roi import ROIInfo
from gauge.models.wire import WireResult
from gauge.models.plate import PlateResult
from gauge.models.grade import GradeResult


class IQIRecord(BaseModel):
    image_path: str
    ok: bool = False
    status: str = "error"
    result_code: int = 9001
    result_name: str = "internal_error"
    result_message: str = "内部异常"
    grade: Optional[int] = None
    iqi_type: Optional[str] = None
    plate_code: Optional[str] = None
    plate_number: Optional[int] = None
    plate_source: Optional[str] = None
    wire_count: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    general_fields_found: bool = False
    iqi_marker_found: bool = False

    fields: GeneralFields = Field(default_factory=GeneralFields)
    field_statistics: FieldStatistics = Field(default_factory=FieldStatistics)
    correction: Dict[str, Any] = Field(default_factory=dict)
    full_image_preprocess: Dict[str, Any] = Field(default_factory=dict)
    preprocess: Dict[str, Any] = Field(default_factory=dict)
    ocr: Optional[OCRResult] = None
    full_image_ocr: Optional[OCRResult] = None
    full_image_plate: Optional[PlateResult] = None
    roi: Optional[ROIInfo] = None
    roi_ocr: Optional[OCRResult] = None
    roi_plate: Optional[PlateResult] = None
    plate: PlateResult = Field(default_factory=PlateResult)
    wire: WireResult = Field(default_factory=WireResult)
    grade_rule: Optional[GradeResult] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    visualization: Dict[str, Any] = Field(default_factory=dict)
    timings_ms: Dict[str, float] = Field(default_factory=dict)
    final_result_vis_path: Optional[str] = None
    status_vis_dir: Optional[str] = None

    _debug_artifacts: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def create_error(cls, code: int, message: str, image_path: str = "") -> "IQIRecord":
        from gauge.domain.iqi_rules import build_result_status
        status = build_result_status(code, message)
        return cls(
            image_path=image_path,
            ok=False,
            status="error",
            result_code=code,
            result_name=status.get("result_name", "unknown_error"),
            result_message=message,
        )
