#!/usr/bin/env python3
"""Plate marker Pydantic models."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlateCandidate(BaseModel):
    code: str
    iqi_type: str
    number: int
    corrections: List[str] = Field(default_factory=list)
    source_text: str = ""


class PlateResult(BaseModel):
    ok: bool = False
    result_code: int = 9001
    result_name: str = "internal_error"
    result_message: str = "内部异常"
    iqi_type: Optional[str] = None
    number: Optional[int] = None
    plate_code: Optional[str] = None
    raw_texts: List[str] = Field(default_factory=list)
    normalized_texts: List[str] = Field(default_factory=list)
    candidate_codes: List[str] = Field(default_factory=list)
    corrections: List[str] = Field(default_factory=list)
    sequence_candidates: Optional[List[str]] = None
    raw_text_items: Optional[List[Dict[str, Any]]] = None
