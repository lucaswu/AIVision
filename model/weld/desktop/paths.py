"""桌面版的路径约定：程序目录、模型默认位置、用户缓存/配置目录。"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, Optional

# model/weld —— run_inference_pipeline.py 所在目录
APP_DIR = Path(__file__).resolve().parents[1]
IQIDDET_DIR = APP_DIR / "IQIDDET"

# 与 run_inference_pipeline.py 的 SUPPORTED_IMAGE_EXTS 保持一致（有测试校验）
SUPPORTED_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".dcm", ".dicom", ".dic", ".diconde")


def user_data_dir() -> Path:
    """配置与引擎缓存的根目录：Windows 用 %LOCALAPPDATA%，其它平台用 ~/.cache。"""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "AIVision"


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "AIVision"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def prepared_cache_dir() -> Path:
    """16bit/DICOM 转 8bit 的中间图目录（不放进输出目录）。"""
    return user_data_dir() / "prepared"


def engine_cache_dir() -> Path:
    return user_data_dir() / "engine_cache"


def weights_dir() -> Path:
    return Path(os.environ.get("AIVISION_WEIGHTS_DIR") or APP_DIR / "weight")


def _first_existing(*candidates: Path) -> Path:
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


@dataclass
class ModelPaths:
    """所有模型文件路径。界面「模型设置」可逐项覆盖。"""

    roi_weights: str = ""
    primary_weights: str = ""
    correction_model: str = ""
    location_model: str = ""
    location2_model: str = ""
    gauge_weights: str = ""
    fclip_ckpt: str = ""
    fclip_config: str = ""
    fclip_params: str = ""
    ocr_det_model_dir: str = ""
    ocr_rec_model_dir: str = ""
    ocr_orientation_model: str = ""

    @classmethod
    def defaults(cls) -> "ModelPaths":
        w = weights_dir()
        iqi = IQIDDET_DIR / "models"
        return cls(
            roi_weights=str(w / "weldROI4.pt"),
            primary_weights=str(_first_existing(w / "primary-weights.pth", w / "0208primary.pth")),
            correction_model=str(w / "weld_orientation_model.pth"),
            location_model=str(w / "location_0.pt"),
            location2_model=str(w / "location_1.pt"),
            gauge_weights=str(iqi / "guagerotation.pt"),
            fclip_ckpt=str(iqi / "fclip67.pth.tar"),
            fclip_config=str(iqi / "fclip_config.yaml"),
            fclip_params=str(IQIDDET_DIR / "params.yaml"),
            ocr_det_model_dir=str(iqi / "PP-OCRv5_server_det"),
            ocr_rec_model_dir=str(iqi / "OCR_rec_inference_best_accuracy0325"),
            ocr_orientation_model=str(iqi / "ocr_orientation_model.pth"),
        )

    def to_dict(self) -> Dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, str]]) -> "ModelPaths":
        merged = cls.defaults()
        for f in fields(cls):
            value = (data or {}).get(f.name)
            if value:
                setattr(merged, f.name, str(value))
        return merged

    def missing(self) -> Dict[str, str]:
        return {k: v for k, v in self.to_dict().items() if not Path(v).exists()}
