#!/usr/bin/env python3
"""Grade computation Pydantic model."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class GradeResult(BaseModel):
    ok: bool = False
    result_code: int = 9001
    result_name: str = "internal_error"
    result_message: str = "内部异常"
    grade: int = 0
    wire_count: Optional[int] = None
