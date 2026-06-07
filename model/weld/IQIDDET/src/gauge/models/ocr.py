#!/usr/bin/env python3
"""OCR-related Pydantic models."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrientationInfo(BaseModel):
    label: Optional[int] = None
    confidence: Optional[float] = None
    status: str = "disabled"
    corrected: bool = False
    actions: Optional[str] = None


class OCRItem(BaseModel):
    crop_index: int = -1
    text: str = ""
    score: Optional[float] = None
    box: List[List[float]] = Field(default_factory=list)
    det_score: Optional[float] = None
    crop_size: Optional[List[int]] = None
    status: str = "ok"
    accepted_by_score: bool = True
    orientation: OrientationInfo = Field(default_factory=OrientationInfo)
    box_image: Optional[List[List[float]]] = None
    box_roi_unrotated: Optional[List[List[float]]] = None
    error: Optional[str] = None


class OCRTimings(BaseModel):
    text_det_ms: float = 0.0
    text_orientation_ms: float = 0.0
    text_rec_ms: float = 0.0
    text_total_ms: float = 0.0


class OCRResult(BaseModel):
    status: str = "error"
    error: Optional[str] = None
    texts: List[str] = Field(default_factory=list)
    scores: List[Optional[float]] = Field(default_factory=list)
    items: List[OCRItem] = Field(default_factory=list)
    all_items: List[OCRItem] = Field(default_factory=list)
    num_items: int = 0
    selected_variant: str = "det_rec"
    all_texts_original: List[str] = Field(default_factory=list)
    all_texts_mirror: List[str] = Field(default_factory=list)
    det_box_count: int = 0
    rec_item_count: int = 0
    jb_items: List[OCRItem] = Field(default_factory=list)
    jb_texts: List[str] = Field(default_factory=list)
    jb_item_count: int = 0
    item_errors: List[Dict[str, Any]] = Field(default_factory=list)
    timings_ms: OCRTimings = Field(default_factory=OCRTimings)
    all_items_original: Optional[List[OCRItem]] = None
    items_original: Optional[List[OCRItem]] = None
    all_items_image: Optional[List[OCRItem]] = None
    items_image: Optional[List[OCRItem]] = None

    @property
    def ok(self) -> bool:
        return self.status in ("ok",)
