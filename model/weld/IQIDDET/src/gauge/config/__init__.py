#!/usr/bin/env python3
"""Centralized configuration for IQI pipeline."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class GaugeConfig(BaseModel):
    weights: str = "models/guagerotation.pt"
    conf: float = 0.25
    iou: float = 0.45
    imgsz: int = 640
    device: Optional[str] = None
    select: Literal["conf", "area"] = "conf"
    class_filter: Optional[int] = Field(default=None, alias="gauge_class")


class FClipConfig(BaseModel):
    ckpt: Optional[str] = None
    device: Optional[str] = None
    fclip_model_config: str = Field(default="config/model.yaml")
    params: str = "params.yaml"
    threshold: Optional[float] = None


class OCRConfig(BaseModel):
    device: Literal["cpu", "gpu"] = "gpu"
    det_model_name: str = "PP-OCRv5_server_det"
    det_model_dir: Optional[str] = None
    rec_model_name: str = "en_PP-OCRv5_mobile_rec"
    rec_model_dir: Optional[str] = None
    det_limit_side_len: int = 960
    det_limit_type: Literal["max", "min"] = "max"
    min_score: float = 0.0
    number_range: str = "1-19"
    enable_orientation: bool = False
    orientation_model: Optional[str] = "models/ocr_orientation_model.pth"
    orientation_device: Optional[str] = None
    orientation_verbose: bool = False


class CorrectionConfig(BaseModel):
    enabled: bool = False
    model: Optional[str] = None
    device: Optional[str] = None
    verbose: bool = False


class EnhanceConfig(BaseModel):
    mode: Literal["original", "windowing"] = "windowing"
    rotate_roi: bool = True


class PipelineConfig(BaseSettings):
    gauge: GaugeConfig = Field(default_factory=GaugeConfig)
    fclip: FClipConfig = Field(default_factory=FClipConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    correction: CorrectionConfig = Field(default_factory=CorrectionConfig)
    enhance: EnhanceConfig = Field(default_factory=EnhanceConfig)

    class Config:
        env_prefix = "IQIDET_"
        env_nested_delimiter = "__"

    def apply_cli_overrides(self, args) -> "PipelineConfig":
        """Apply argparse Namespace overrides. CLI args take precedence over defaults/env."""
        updates: dict = {}
        mapping = {
            "gauge_weights": ("gauge", "weights"),
            "gauge_conf": ("gauge", "conf"),
            "gauge_iou": ("gauge", "iou"),
            "gauge_imgsz": ("gauge", "imgsz"),
            "gauge_device": ("gauge", "device"),
            "gauge_select": ("gauge", "select"),
            "gauge_class": ("gauge", "class_filter"),
            "fclip_ckpt": ("fclip", "ckpt"),
            "fclip_device": ("fclip", "device"),
            "fclip_config": ("fclip", "fclip_model_config"),
            "fclip_params": ("fclip", "params"),
            "fclip_threshold": ("fclip", "threshold"),
            "ocr_device": ("ocr", "device"),
            "ocr_det_model_name": ("ocr", "det_model_name"),
            "ocr_det_model_dir": ("ocr", "det_model_dir"),
            "ocr_rec_model_name": ("ocr", "rec_model_name"),
            "ocr_rec_model_dir": ("ocr", "rec_model_dir"),
            "ocr_det_limit_side_len": ("ocr", "det_limit_side_len"),
            "ocr_det_limit_type": ("ocr", "det_limit_type"),
            "ocr_min_score": ("ocr", "min_score"),
            "ocr_number_range": ("ocr", "number_range"),
            "enable_ocr_orientation": ("ocr", "enable_orientation"),
            "ocr_orientation_model": ("ocr", "orientation_model"),
            "ocr_orientation_device": ("ocr", "orientation_device"),
            "enable_correction": ("correction", "enabled"),
            "correction_model": ("correction", "model"),
            "correction_device": ("correction", "device"),
            "correction_verbose": ("correction", "verbose"),
            "enhance_mode": ("enhance", "mode"),
            "no_rotate": ("enhance", "rotate_roi"),
        }
        for attr_name, config_path in mapping.items():
            value = getattr(args, attr_name, None)
            if value is None or value is False:
                continue
            section, key = config_path
            updates.setdefault(section, {})
            updates[section][key] = False if attr_name == "no_rotate" else value
        if getattr(args, "ocr_orientation_verbose", False):
            updates.setdefault("ocr", {})["orientation_verbose"] = True
        if not updates:
            return self

        data = self.model_dump()
        for section, section_updates in updates.items():
            data.setdefault(section, {})
            data[section].update(section_updates)
        return PipelineConfig.model_validate(data)
