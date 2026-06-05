#!/usr/bin/env python3
"""General fields extraction Pydantic models."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldRecord(BaseModel):
    text: str = ""
    match_text: str = ""
    score: Optional[float] = None
    box: Optional[List[List[float]]] = None
    crop_index: Optional[int] = None
    value: Optional[str] = None


class WeldFilmPair(BaseModel):
    text: str = ""
    match_text: str = ""
    score: Optional[float] = None
    box: Optional[List[List[float]]] = None
    crop_index: Optional[int] = None
    weld_no: str = ""
    film_no: str = ""
    separator: str = ""


class PipeSpec(BaseModel):
    text: str = ""
    match_text: str = ""
    score: Optional[float] = None
    box: Optional[List[List[float]]] = None
    crop_index: Optional[int] = None
    value: str = ""
    outer_diameter: str = ""
    wall_thickness: str = ""


class GeneralFields(BaseModel):
    component_codes: List[FieldRecord] = Field(default_factory=list)
    weld_film_pairs: List[WeldFilmPair] = Field(default_factory=list)
    weld_numbers: List[FieldRecord] = Field(default_factory=list)
    film_numbers: List[FieldRecord] = Field(default_factory=list)
    pipe_specs: List[PipeSpec] = Field(default_factory=list)


class FieldStatistics(BaseModel):
    component_code_count: int = 0
    weld_film_pair_count: int = 0
    weld_number_count: int = 0
    film_number_count: int = 0
    pipe_spec_count: int = 0
    general_fields_found: bool = False
    full_image_marker_found: bool = False
    roi_marker_found: bool = False
    iqi_marker_found: bool = False
