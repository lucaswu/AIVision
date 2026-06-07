#!/usr/bin/env python3
"""Shared IQI inference service for delivery and debug wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from gauge.config import (
    CorrectionConfig,
    EnhanceConfig,
    FClipConfig,
    GaugeConfig,
    OCRConfig,
    PipelineConfig,
)
from gauge.services.fclip.inferencer import FClipInferencer
from gauge.imaging.geometry import invert_perspective_matrix, perspective_transform_points, undo_ccw90_points
from gauge.domain.iqi_rules import (
    build_result_status,
    choose_primary_result_code,
    format_allowed_numbers_spec,
    infer_plate_from_texts,
    normalize_text,
    parse_allowed_numbers_spec,
)
from gauge.domain.record_builders import build_delivery_record, build_iqi_statistics
from gauge.runtime.ocr_runtime import PaddleOCRSubprocessClient


class IQIInferencer:
    """Shared service for complete IQI grade inference."""

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        **kwargs: Any,
    ):
        # ---- Build config from kwargs if not provided (legacy path) ----
        if config is not None:
            self.config = config
        else:
            gauge_weights = kwargs.pop("gauge_weights", "")
            fclip_ckpt = kwargs.pop("fclip_ckpt", None)
            gauge_conf = float(kwargs.pop("gauge_conf", 0.25))
            gauge_iou = float(kwargs.pop("gauge_iou", 0.45))
            gauge_imgsz = int(kwargs.pop("gauge_imgsz", 640))
            gauge_device = kwargs.pop("gauge_device", None)
            gauge_select = str(kwargs.pop("gauge_select", "conf"))
            gauge_class = kwargs.pop("gauge_class", None)
            enhance_mode = str(kwargs.pop("enhance_mode", "windowing"))
            rotate_roi = bool(kwargs.pop("rotate_roi", True))
            enable_correction = bool(kwargs.pop("enable_correction", False))
            correction_model = kwargs.pop("correction_model", None)
            correction_device = kwargs.pop("correction_device", None)
            correction_verbose = bool(kwargs.pop("correction_verbose", False))
            ocr_device = str(kwargs.pop("ocr_device", "gpu"))
            ocr_det_model_name = str(kwargs.pop("ocr_det_model_name", "PP-OCRv5_server_det"))
            ocr_det_model_dir = kwargs.pop("ocr_det_model_dir", None)
            ocr_rec_model_name = str(kwargs.pop("ocr_rec_model_name", "en_PP-OCRv5_mobile_rec"))
            ocr_rec_model_dir = kwargs.pop("ocr_rec_model_dir", None)
            ocr_det_limit_side_len = int(kwargs.pop("ocr_det_limit_side_len", 960))
            ocr_det_limit_type = str(kwargs.pop("ocr_det_limit_type", "max"))
            ocr_min_score = float(kwargs.pop("ocr_min_score", 0.0))
            enable_ocr_orientation = bool(kwargs.pop("enable_ocr_orientation", False))
            ocr_orientation_model = kwargs.pop("ocr_orientation_model", None)
            ocr_orientation_device = kwargs.pop("ocr_orientation_device", None)
            ocr_orientation_verbose = bool(kwargs.pop("ocr_orientation_verbose", False))
            ocr_number_range = kwargs.pop("ocr_number_range", None)
            fclip_device = kwargs.pop("fclip_device", None)
            fclip_model_config = kwargs.pop("fclip_model_config", "config/model.yaml")
            fclip_params = kwargs.pop("fclip_params", "params.yaml")
            fclip_threshold = kwargs.pop("fclip_threshold", None)

            self.config = PipelineConfig(
                gauge=GaugeConfig(
                    weights=gauge_weights,
                    conf=gauge_conf,
                    iou=gauge_iou,
                    imgsz=gauge_imgsz,
                    device=gauge_device,
                    select=gauge_select,
                    gauge_class=gauge_class,
                ),
                fclip=FClipConfig(
                    ckpt=fclip_ckpt,
                    device=fclip_device,
                    fclip_model_config=str(Path(fclip_model_config).resolve()),
                    params=str(Path(fclip_params).resolve()),
                    threshold=fclip_threshold,
                ),
                ocr=OCRConfig(
                    device=ocr_device,
                    det_model_name=ocr_det_model_name,
                    det_model_dir=ocr_det_model_dir,
                    rec_model_name=ocr_rec_model_name,
                    rec_model_dir=ocr_rec_model_dir,
                    det_limit_side_len=ocr_det_limit_side_len,
                    det_limit_type=ocr_det_limit_type,
                    min_score=ocr_min_score,
                    enable_orientation=enable_ocr_orientation,
                    orientation_model=ocr_orientation_model,
                    orientation_device=ocr_orientation_device,
                    orientation_verbose=ocr_orientation_verbose,
                    number_range=format_allowed_numbers_spec(
                        parse_allowed_numbers_spec(
                            ocr_number_range
                            if not isinstance(ocr_number_range, (list, tuple))
                            else format_allowed_numbers_spec(ocr_number_range)
                        )
                    ),
                ),
                correction=CorrectionConfig(
                    enabled=enable_correction,
                    model=correction_model,
                    device=correction_device,
                    verbose=correction_verbose,
                ),
                enhance=EnhanceConfig(
                    mode=enhance_mode,
                    rotate_roi=rotate_roi,
                ),
            )

        # ---- Store legacy attr aliases for backward compatibility ----
        self.gauge_weights = str(self.config.gauge.weights)
        self.fclip_ckpt = self.config.fclip.ckpt
        self.gauge_conf = float(self.config.gauge.conf)
        self.gauge_iou = float(self.config.gauge.iou)
        self.gauge_imgsz = int(self.config.gauge.imgsz)
        self.gauge_device = self.config.gauge.device
        self.gauge_select = str(self.config.gauge.select)
        self.gauge_class = self.config.gauge.class_filter
        self.enhance_mode = str(self.config.enhance.mode)
        self.rotate_roi = bool(self.config.enhance.rotate_roi)
        self.correction_verbose = bool(self.config.correction.verbose)
        self.ocr_det_limit_side_len = int(self.config.ocr.det_limit_side_len)
        self.ocr_det_limit_type = str(self.config.ocr.det_limit_type)
        self.ocr_min_score = float(self.config.ocr.min_score)
        self.ocr_orientation_verbose = bool(self.config.ocr.orientation_verbose)
        self.ocr_allowed_numbers = parse_allowed_numbers_spec(self.config.ocr.number_range)
        self.ocr_number_range = format_allowed_numbers_spec(self.ocr_allowed_numbers)
        self.fclip_model_config = str(self.config.fclip.fclip_model_config)
        self.fclip_params = str(self.config.fclip.params)
        self.fclip_threshold = self.config.fclip.threshold

        # ---- Model initialization (kept from original) ----
        self.corrector = None
        if self.config.correction.enabled:
            if not self.config.correction.model:
                raise ValueError("--correction-model is required when enable_correction=True")
            from gauge.services.orientation.weld import WeldOrientationCorrector

            self.corrector = WeldOrientationCorrector(
                model_path=self.config.correction.model,
                model_type="resnet50",
                device=self.config.correction.device,
            )

        self.ocr_text_corrector = None
        if self.config.ocr.enable_orientation:
            if not self.config.ocr.orientation_model:
                raise ValueError("--ocr-orientation-model is required when enable_ocr_orientation=True")
            from gauge.services.orientation.ocr_text import OCRTextOrientationCorrector

            model_path = Path(self.config.ocr.orientation_model)
            if not model_path.is_absolute():
                model_path = (Path.cwd() / model_path).resolve()
            self.ocr_text_corrector = OCRTextOrientationCorrector(
                model_path=model_path,
                model_type="resnet34",
                device=self.config.ocr.orientation_device,
            )

        from ultralytics import YOLO

        self.gauge_model = YOLO(self.gauge_weights)
        self.ocr_backend = PaddleOCRSubprocessClient(
            device=self.config.ocr.device,
            det_model_name=self.config.ocr.det_model_name,
            det_model_dir=self.config.ocr.det_model_dir,
            rec_model_name=self.config.ocr.rec_model_name,
            rec_model_dir=self.config.ocr.rec_model_dir,
            det_limit_side_len=self.ocr_det_limit_side_len,
            det_limit_type=self.ocr_det_limit_type,
        )
        self.fclip_inferencer = None
        if self.fclip_ckpt:
            self.fclip_inferencer = FClipInferencer(
                ckpt_path=self.fclip_ckpt,
                device=self.config.fclip.device,
                model_config=self.fclip_model_config,
                params_file=self.fclip_params,
                threshold=self.fclip_threshold,
            )

        # ---- Build PipelineRunner ----
        from gauge.pipeline.runner import PipelineRunner

        services: Dict[str, Any] = {
            "gauge_model": self.gauge_model,
            "ocr_backend": self.ocr_backend,
            "fclip_inferencer": self.fclip_inferencer,
            "corrector": self.corrector,
            "ocr_text_corrector": self.ocr_text_corrector,
        }
        self.runner = PipelineRunner.from_config(self.config, services=services)

    def close(self) -> None:
        if self.ocr_backend is not None:
            self.ocr_backend.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def get_runtime_meta(self) -> Dict[str, Any]:
        return {
            "gauge_weights": self.gauge_weights,
            "fclip_ckpt": self.fclip_ckpt,
            "fclip_model_config": self.fclip_model_config,
            "fclip_params": self.fclip_params,
            "fclip_threshold": self.fclip_threshold,
            "gauge_conf": self.gauge_conf,
            "gauge_iou": self.gauge_iou,
            "gauge_imgsz": self.gauge_imgsz,
            "gauge_select": self.gauge_select,
            "gauge_class": self.gauge_class,
            "enhance_mode": self.enhance_mode,
            "rotation_rule": "ccw90_if_width_gt_height" if self.rotate_roi else "disabled",
            "ocr_min_score": self.ocr_min_score,
            "ocr_number_range": self.ocr_number_range,
            "ocr_det_limit_side_len": self.ocr_det_limit_side_len,
            "ocr_det_limit_type": self.ocr_det_limit_type,
            "full_image_resize_long_side": self.ocr_det_limit_side_len,
            "full_image_ocr_enhance_mode": "windowing",
            "ocr_runtime": "subprocess_det_rec",
        }

    # ------------------------------------------------------------------
    # Legacy static/class helper methods (kept for backward compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_skipped_wire(status: str, error: Optional[str] = None) -> Dict[str, Any]:
        from gauge.domain.record_builders import build_skipped_wire

        return build_skipped_wire(status, error)

    @staticmethod
    def _scale_box_points(box: Any, scale: float) -> Any:
        from gauge.imaging.geometry import scale_box_points

        return scale_box_points(box, scale)

    @classmethod
    def _scale_ocr_items_to_original(cls, items: Sequence[Dict[str, Any]], scale: float) -> List[Dict[str, Any]]:
        from gauge.imaging.geometry import scale_ocr_items_to_original

        return scale_ocr_items_to_original(items, scale)

    @classmethod
    def _scale_roi_info_to_original(cls, roi_info: Dict[str, Any], scale: float) -> Dict[str, Any]:
        from gauge.imaging.geometry import scale_roi_info_to_original

        return scale_roi_info_to_original(roi_info, scale)

    @staticmethod
    def _is_usable_ocr_item(item: Dict[str, Any]) -> bool:
        from gauge.imaging.geometry import is_usable_ocr_item

        return is_usable_ocr_item(item)

    @staticmethod
    def _box_points_to_bbox(box: Any) -> Optional[List[float]]:
        from gauge.imaging.geometry import box_points_to_bbox

        return box_points_to_bbox(box)

    @staticmethod
    def _project_roi_box_to_image(
        box: Any,
        crop_inverse_matrix: Optional[np.ndarray],
        pre_rotate_size: Optional[Sequence[int]],
        rotated: bool,
    ) -> Tuple[Any, Any]:
        if box is None:
            return None, None
        try:
            roi_points = np.asarray(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            return None, None
        if roi_points.size == 0:
            return None, None

        roi_unrotated = roi_points
        if rotated:
            if pre_rotate_size is None:
                return roi_points.tolist(), None
            roi_unrotated = undo_ccw90_points(roi_points, pre_rotate_size=pre_rotate_size)

        if crop_inverse_matrix is None:
            return roi_points.tolist(), roi_unrotated.tolist()

        image_points = perspective_transform_points(roi_unrotated, crop_inverse_matrix)
        return image_points.tolist(), roi_unrotated.tolist()

    @classmethod
    def _project_ocr_items_to_image(
        cls,
        items: Sequence[Dict[str, Any]],
        crop_inverse_matrix: Optional[np.ndarray],
        pre_rotate_size: Optional[Sequence[int]],
        rotated: bool,
    ) -> List[Dict[str, Any]]:
        projected_items: List[Dict[str, Any]] = []
        for item in items:
            projected = dict(item)
            box_image, box_unrotated = cls._project_roi_box_to_image(
                item.get("box"),
                crop_inverse_matrix=crop_inverse_matrix,
                pre_rotate_size=pre_rotate_size,
                rotated=rotated,
            )
            projected["box_image"] = box_image
            projected["box_roi_unrotated"] = box_unrotated
            projected_items.append(projected)
        return projected_items

    @classmethod
    def _build_plate_visualization_items(
        cls,
        items: Sequence[Dict[str, Any]],
        source: str,
    ) -> List[Dict[str, Any]]:
        from gauge.imaging.visualization import build_plate_visualization_items

        return build_plate_visualization_items(items, source)

    @staticmethod
    def _select_plate_visualization_items(
        items: Sequence[Dict[str, Any]],
        plate_code: Optional[str],
        allowed_numbers: Optional[Sequence[int]],
    ) -> List[Dict[str, Any]]:
        target_code = normalize_text(plate_code)
        if not target_code:
            return []

        selected: List[Dict[str, Any]] = []
        for item in items:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            parsed = infer_plate_from_texts(
                [text],
                require_jb=True,
                allowed_numbers=allowed_numbers,
            )
            candidates = [normalize_text(code) for code in (parsed.get("candidate_codes") or [])]
            if target_code in candidates:
                selected.append(item)
        return selected

    def _attach_visualization_payload(
        self,
        record: Dict[str, Any],
        *,
        roi_plate_vis_items: Optional[Sequence[Dict[str, Any]]] = None,
        full_plate_vis_items: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> None:
        roi = record.get("roi") or {}
        plate = record.get("plate") or {}
        wire = record.get("wire") or {}
        plate_source = str(record.get("plate_source") or "")

        if plate_source == "roi":
            plate_items = list(roi_plate_vis_items or [])
        elif plate_source == "full_image":
            plate_items = list(full_plate_vis_items or [])
        else:
            plate_items = []

        plate_items_selected = self._select_plate_visualization_items(
            plate_items,
            plate_code=plate.get("plate_code"),
            allowed_numbers=self.ocr_allowed_numbers,
        )

        wire_lines = []
        for line in wire.get("lines") or []:
            image_xy = line.get("image_xy")
            if not image_xy:
                continue
            wire_lines.append(
                {
                    "index": line.get("index"),
                    "score": line.get("score"),
                    "image_xy": image_xy,
                }
            )

        record["visualization"] = {
            "roi_polygon_xy": roi.get("polygon"),
            "roi_bbox": roi.get("bbox"),
            "plate_source": plate_source,
            "plate_code": plate.get("plate_code"),
            "candidate_codes": plate.get("candidate_codes") or [],
            "raw_texts": plate.get("raw_texts") or [],
            "plate_text_items": plate_items,
            "plate_text_items_selected": plate_items_selected,
            "wire_lines": wire_lines,
        }

    @staticmethod
    def _merge_prefixed_ocr_timings(
        step_timings: Dict[str, float],
        prefix: str,
        ocr_result: Optional[Dict[str, Any]],
    ) -> None:
        if not ocr_result:
            return
        for key, value in (ocr_result.get("timings_ms") or {}).items():
            normalized_key = str(key)
            if normalized_key == "text_total_ms":
                step_timings[f"{prefix}_ocr_ms"] = float(value)
            else:
                step_timings[f"{prefix}_{normalized_key}"] = float(value)

    @staticmethod
    def _finalize_record(
        record: Dict[str, Any],
        error_entries: Sequence[Dict[str, Any]],
        warnings: Sequence[str],
        grade: Optional[int] = None,
    ) -> Dict[str, Any]:
        primary_code = choose_primary_result_code([entry["result_code"] for entry in error_entries])
        status = build_result_status(primary_code)
        record.update(status)
        record["status"] = "ok" if primary_code == 0 else "error"
        record["errors"] = list(error_entries)
        record["warnings"] = list(warnings)

        plate = record.get("plate") or {}
        wire = record.get("wire") or {}
        record["iqi_type"] = plate.get("iqi_type")
        record["plate_code"] = plate.get("plate_code")
        record["plate_number"] = plate.get("number")
        record["wire_count"] = wire.get("wire_count")
        record["iqi_marker_found"] = bool(plate.get("ok"))
        record["general_fields_found"] = bool((record.get("field_statistics") or {}).get("general_fields_found", False))
        record["grade"] = int(grade) if primary_code == 0 and grade is not None else None
        return record

    # ------------------------------------------------------------------
    # Main inference entry point
    # ------------------------------------------------------------------

    def infer_image_path(
        self,
        image_path: Path,
        return_debug_artifacts: bool = False,
        debug_timer: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, np.ndarray]]]:
        try:
            record = self.runner.run(
                image_path,
                return_debug_artifacts=return_debug_artifacts,
            )
            return record.model_dump(), record._debug_artifacts
        except Exception as exc:
            from gauge.domain.iqi_rules import build_result_status

            record: Dict[str, Any] = {
                "image_path": str(image_path),
                "status": "error",
                "ok": False,
                "result_code": 9001,
                "result_name": "internal_error",
                "result_message": str(exc),
                "grade": None,
                "iqi_type": None,
                "plate_code": None,
                "plate_number": None,
                "plate_source": None,
                "wire_count": None,
                "fields": {
                    "component_codes": [],
                    "weld_film_pairs": [],
                    "weld_numbers": [],
                    "film_numbers": [],
                    "pipe_specs": [],
                },
                "field_statistics": {
                    "component_code_count": 0,
                    "weld_film_pair_count": 0,
                    "weld_number_count": 0,
                    "film_number_count": 0,
                    "pipe_spec_count": 0,
                    "general_fields_found": False,
                    "full_image_marker_found": False,
                    "roi_marker_found": False,
                    "iqi_marker_found": False,
                },
                "warnings": [],
                "errors": [{"stage": "pipeline", **build_result_status(9001, str(exc))}],
            }
            return record, None
