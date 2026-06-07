#!/usr/bin/env python3
"""ROI-related Pydantic models."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class ROIInfo(BaseModel):
    polygon: List[List[float]]
    bbox: List[float]
    conf: Optional[float] = None
    class_id: Optional[int] = None
    crop_size_before_rotate: Optional[List[int]] = None
    crop_inverse_matrix: Optional[List[List[float]]] = None
