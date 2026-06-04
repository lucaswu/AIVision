#!/usr/bin/env python3
"""StageContext — mutable state flowing through pipeline stages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from gauge.config import PipelineConfig
from gauge.models.record import IQIRecord


class StageContext(BaseModel):
    """Mutable state flowing through pipeline stages.

    Each stage reads from and writes to this context,
    building up the complete result incrementally.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input
    image_path: str
    config: PipelineConfig

    # Image (set by ImageLoadStage)
    image: Optional[np.ndarray] = None
    height: Optional[int] = None
    width: Optional[int] = None

    # Correction (set by CorrectionStage)
    correction_info: Dict[str, Any] = Field(default_factory=dict)

    # Full image OCR (set by FullImageOCRStage)
    sampled_image: Optional[np.ndarray] = None
    resize_scale: float = 1.0
    full_ocr_result: Optional[Dict[str, Any]] = None
    full_plate_result: Optional[Dict[str, Any]] = None
    full_plate_vis_items: List[Dict[str, Any]] = Field(default_factory=list)
    general_fields_data: Dict[str, Any] = Field(default_factory=dict)
    field_statistics: Dict[str, Any] = Field(default_factory=dict)

    # ROI detection (set by ROIDetectStage)
    roi_info: Optional[Dict[str, Any]] = None
    roi_cropped: Optional[np.ndarray] = None
    roi_image: Optional[np.ndarray] = None
    roi_gray: Optional[np.ndarray] = None
    roi_crop_matrix: Optional[np.ndarray] = None
    pre_rotate_size: Optional[List[int]] = None
    rotated: bool = False

    # ROI OCR (set by ROIOCRStage)
    roi_ocr_result: Optional[Dict[str, Any]] = None
    roi_plate_result: Optional[Dict[str, Any]] = None
    roi_plate_vis_items: List[Dict[str, Any]] = Field(default_factory=list)

    # Wire detection (set by WireDetectStage)
    wire_result: Optional[Dict[str, Any]] = None

    # Grade fusion (set by GradeFusionStage)
    grade_result: Optional[Dict[str, Any]] = None

    # Selected plate
    plate_result: Optional[Dict[str, Any]] = None
    plate_source: Optional[str] = None

    # Tracking
    record_errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    timings_ms: Dict[str, float] = Field(default_factory=dict)

    # Debug
    debug_artifacts: Optional[Dict[str, np.ndarray]] = None
    _debug_artifacts: Optional[Dict[str, np.ndarray]] = None

    def to_record(self) -> IQIRecord:
        """Build the final IQIRecord from current context state."""
        from gauge.domain.record_builders import build_iqi_record

        record = build_iqi_record(self)
        if self.debug_artifacts is not None:
            record._debug_artifacts = self.debug_artifacts
        return record
