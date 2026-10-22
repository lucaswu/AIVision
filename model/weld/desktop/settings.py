"""界面设置的持久化（JSON）。读写失败一律忽略，不影响程序运行。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List

from . import paths


@dataclass
class UiSettings:
    inputs: List[str] = field(default_factory=list)
    output_dir: str = ""
    recursive: bool = True
    mode: str = "det"
    device: str = "cuda:0"
    primary_conf: float = 0.15
    wide_slice: bool = True
    enable_correction: bool = True
    enable_location: bool = True
    location_conf: float = 0.6
    enable_location2: bool = True
    location2_conf: float = 0.25
    enable_iqi: bool = True
    save_annotated: bool = True
    enable_competition: bool = False
    competition_default_spec: str = ""
    competition_info_table: str = ""  # 《影像信息表》.xlsx/.xls/.csv，或逐图规格 JSON
    competition_fast: bool = True
    competition_strict_pipe_table26: bool = False
    competition_split_pores: bool = False
    competition_merge_gap_mm: float = 2.0
    competition_intermittent_length: str = "envelope"
    competition_report_plate_root: bool = False  # 默认不填报板上的根部内凹/咬边
    competition_deadline_min: float = 37.0
    models: Dict[str, str] = field(default_factory=dict)  # 仅保存与默认值不同的项

    @classmethod
    def load(cls) -> "UiSettings":
        try:
            raw: Dict[str, Any] = json.loads(paths.settings_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        names = {f.name for f in fields(cls)}
        obj = cls()
        for key, value in raw.items():
            if key in names and isinstance(value, type(getattr(obj, key))):
                setattr(obj, key, value)
        return obj

    def save(self) -> None:
        try:
            target = paths.settings_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            data = {f.name: getattr(self, f.name) for f in fields(self)}
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
