#!/usr/bin/env python3
"""Wire detection Pydantic models."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class LineRecord(BaseModel):
    index: int
    score: Optional[float] = None
    roi_xy: List[List[float]]
    roi_unrotated_xy: Optional[List[List[float]]] = None
    image_xy: Optional[List[List[float]]] = None


class WireResult(BaseModel):
    status: str = "error"
    error: Optional[str] = None
    wire_count: Optional[int] = None
    parsed_line_count: int = 0
    lines: List[LineRecord] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok" and self.wire_count is not None
