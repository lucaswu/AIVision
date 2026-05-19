#!/usr/bin/env python3
"""Shared IQI inference service for delivery and debug wrappers."""

from __future__ import annotations

from collections import Counter
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from gauge.fclip_stage import (
    FClipInferencer,
    invert_perspective_matrix,
    perspective_transform_points,
    undo_ccw90_points,
)
from gauge.iqi_rules import (
    build_result_status,
    choose_primary_result_code,
    compute_iqi_grade,
    extract_general_fields_from_ocr_items,
    format_allowed_numbers_spec,
    infer_plate_from_ocr_items,
    infer_plate_from_texts,
    normalize_text,
    parse_allowed_numbers_spec,
    summarize_result_codes,
    summarize_result_codes_named,
)
from gauge.ocr_stage import (
    PaddleOCRSubprocessClient,
    build_ocr_item_debug_images,
    build_ocr_statistics,
    draw_ocr_on_roi,
    infer_roi_ocr,
)
from gauge.pipeline_utils import (
    collect_images,
    crop_rotated_polygon,
    enhance_windowing_gray,
    ensure_dir,
    load_image,
    resize_long_side,
    rotate_if_wide,
    to_gray,
)
from gauge.roi_stage import build_roi_vis_image, extract_best_obb


class IQIInferencer:
    """Shared service for complete IQI grade inference."""

    def __init__(
        self,
        gauge_weights: str,
        fclip_ckpt: Optional[str] = None,
        gauge_conf: float = 0.25,
        gauge_iou: float = 0.45,
        gauge_imgsz: int = 640,
        gauge_device: Optional[str] = None,
        gauge_select: str = "conf",
        gauge_class: Optional[int] = None,
        enhance_mode: str = "windowing",
        rotate_roi: bool = True,
        enable_correction: bool = False,
        correction_model: Optional[str] = None,
        correction_device: Optional[str] = None,
        correction_verbose: bool = False,
        ocr_device: str = "gpu",
        ocr_det_model_name: str = "PP-OCRv5_server_det",
        ocr_det_model_dir: Optional[str] = None,
        ocr_rec_model_name: str = "en_PP-OCRv5_mobile_rec",
        ocr_rec_model_dir: Optional[str] = None,
        ocr_det_limit_side_len: int = 960,
        ocr_det_limit_type: str = "max",
        ocr_min_score: float = 0.0,
        enable_ocr_orientation: bool = False,
        ocr_orientation_model: Optional[str] = None,
        ocr_orientation_device: Optional[str] = None,
        ocr_orientation_verbose: bool = False,
        ocr_number_range: Optional[Sequence[int] | str] = None,
        fclip_device: Optional[str] = None,
        fclip_model_config: str = "config/model.yaml",
        fclip_params: str = "params.yaml",
        fclip_threshold: Optional[float] = None,
    ):
        self.gauge_weights = str(gauge_weights)
        self.fclip_ckpt = str(fclip_ckpt) if fclip_ckpt else None
        self.gauge_conf = float(gauge_conf)
        self.gauge_iou = float(gauge_iou)
        self.gauge_imgsz = int(gauge_imgsz)
        self.gauge_device = gauge_device
        self.gauge_select = str(gauge_select)
        self.gauge_class = gauge_class
        self.enhance_mode = str(enhance_mode)
        self.rotate_roi = bool(rotate_roi)
        self.correction_verbose = bool(correction_verbose)
        self.ocr_det_limit_side_len = int(ocr_det_limit_side_len) if ocr_det_limit_side_len is not None else 960
        self.ocr_det_limit_type = str(ocr_det_limit_type or "max")
        self.ocr_min_score = float(ocr_min_score)
        self.ocr_orientation_verbose = bool(ocr_orientation_verbose)
        if isinstance(ocr_number_range, str) or ocr_number_range is None:
            self.ocr_allowed_numbers = parse_allowed_numbers_spec(ocr_number_range)
        else:
            self.ocr_allowed_numbers = frozenset(int(x) for x in ocr_number_range)
        self.ocr_number_range = format_allowed_numbers_spec(self.ocr_allowed_numbers)
        self.fclip_model_config = str(Path(fclip_model_config).resolve())
        self.fclip_params = str(Path(fclip_params).resolve())
        self.fclip_threshold = fclip_threshold

        self.corrector = None
        if enable_correction:
            if not correction_model:
                raise ValueError("--correction-model is required when enable_correction=True")
            from gauge.weld_correction import WeldOrientationCorrector

            self.corrector = WeldOrientationCorrector(
                model_path=correction_model,
                model_type="resnet50",
                device=correction_device,
            )

        self.ocr_text_corrector = None
        if enable_ocr_orientation:
            if not ocr_orientation_model:
                raise ValueError("--ocr-orientation-model is required when enable_ocr_orientation=True")
            from gauge.ocr_orientation import OCRTextOrientationCorrector

            model_path = Path(ocr_orientation_model)
            if not model_path.is_absolute():
                model_path = (Path.cwd() / model_path).resolve()
            self.ocr_text_corrector = OCRTextOrientationCorrector(
                model_path=model_path,
                model_type="resnet34",
                device=ocr_orientation_device,
            )

        from ultralytics import YOLO

        self.gauge_model = YOLO(self.gauge_weights)
        self.ocr_backend = PaddleOCRSubprocessClient(
            device=ocr_device,
            det_model_name=ocr_det_model_name,
            det_model_dir=ocr_det_model_dir,
            rec_model_name=ocr_rec_model_name,
            rec_model_dir=ocr_rec_model_dir,
            det_limit_side_len=self.ocr_det_limit_side_len,
            det_limit_type=self.ocr_det_limit_type,
        )
        self.fclip_inferencer = None
        if self.fclip_ckpt:
            self.fclip_inferencer = FClipInferencer(
                ckpt_path=self.fclip_ckpt,
                device=fclip_device,
                model_config=self.fclip_model_config,
                params_file=self.fclip_params,
                threshold=fclip_threshold,
            )

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

    @staticmethod
    def _build_skipped_wire(status: str, error: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "status": str(status),
            "wire_count": None,
            "parsed_line_count": 0,
            "lines": [],
            "warnings": [],
        }
        if error:
            payload["error"] = str(error)
        return payload

    @staticmethod
    def _scale_box_points(box: Any, scale: float) -> Any:
        if box is None or scale == 1.0:
            return box
        try:
            pts = np.array(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            return box
        pts = pts / float(scale)
        return pts.tolist()

    @classmethod
    def _scale_ocr_items_to_original(cls, items: Sequence[Dict[str, Any]], scale: float) -> List[Dict[str, Any]]:
        if scale == 1.0:
            return [dict(item) for item in items]
        scaled_items: List[Dict[str, Any]] = []
        for item in items:
            scaled = dict(item)
            scaled["box"] = cls._scale_box_points(item.get("box"), scale)
            scaled_items.append(scaled)
        return scaled_items

    @classmethod
    def _scale_roi_info_to_original(cls, roi_info: Dict[str, Any], scale: float) -> Dict[str, Any]:
        if scale == 1.0:
            return dict(roi_info)
        mapped = dict(roi_info)
        polygon = cls._scale_box_points(roi_info.get("polygon"), scale)
        mapped["polygon"] = polygon
        bbox = roi_info.get("bbox")
        if bbox is not None:
            mapped["bbox"] = [float(value) / float(scale) for value in bbox]
        return mapped

    @staticmethod
    def _is_usable_ocr_item(item: Dict[str, Any]) -> bool:
        return bool(
            str(item.get("text", "")).strip()
            and item.get("status") != "error"
            and item.get("accepted_by_score", True)
        )

    @staticmethod
    def _box_points_to_bbox(box: Any) -> Optional[List[float]]:
        if box is None:
            return None
        try:
            pts = np.asarray(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            return None
        if pts.size == 0:
            return None
        return [
            float(np.min(pts[:, 0])),
            float(np.min(pts[:, 1])),
            float(np.max(pts[:, 0])),
            float(np.max(pts[:, 1])),
        ]

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
        vis_items: List[Dict[str, Any]] = []
        text_index = 0
        for item in items:
            if not cls._is_usable_ocr_item(item):
                continue
            box_image = item.get("box_image")
            if box_image is None:
                box_image = item.get("box")
            vis_items.append(
                {
                    "text_index": int(text_index),
                    "crop_index": item.get("crop_index"),
                    "source": str(source),
                    "text": str(item.get("text", "")),
                    "normalized_text": normalize_text(item.get("text", "")),
                    "score": item.get("score"),
                    "det_score": item.get("det_score"),
                    "status": item.get("status"),
                    "accepted_by_score": bool(item.get("accepted_by_score", True)),
                    "box_image_xy": box_image,
                    "bbox_image": cls._box_points_to_bbox(box_image),
                    "box_roi_xy": item.get("box") if source == "roi" else None,
                    "bbox_roi": cls._box_points_to_bbox(item.get("box")) if source == "roi" else None,
                }
            )
            text_index += 1
        return vis_items

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

    def infer_image_path(
        self,
        image_path: Path,
        return_debug_artifacts: bool = False,
        debug_timer: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, np.ndarray]]]:
        debug_artifacts: Optional[Dict[str, np.ndarray]] = {} if return_debug_artifacts else None
        pipeline_start = time.perf_counter()
        step_timings: Dict[str, float] = {}

        def _mark(step_name: str, start_time: float) -> None:
            if debug_timer:
                step_timings[step_name] = (time.perf_counter() - start_time) * 1000.0

        def _attach_timing(target: Dict[str, Any]) -> None:
            if debug_timer:
                total_ms = (time.perf_counter() - pipeline_start) * 1000.0
                target["timings_ms"] = {
                    key: round(float(value), 3)
                    for key, value in {**step_timings, "total_ms": total_ms}.items()
                }

        def _build_skipped_ocr(status: str, error: Optional[str] = None) -> Dict[str, Any]:
            payload: Dict[str, Any] = {
                "status": str(status),
                "texts": [],
                "scores": [],
                "items": [],
                "all_items": [],
                "num_items": 0,
                "selected_variant": str(status),
                "all_texts_original": [],
                "all_texts_mirror": [],
                "det_box_count": 0,
                "rec_item_count": 0,
                "jb_items": [],
                "jb_texts": [],
                "jb_item_count": 0,
                "item_errors": [],
                "timings_ms": {
                    "text_det_ms": 0.0,
                    "text_orientation_ms": 0.0,
                    "text_rec_ms": 0.0,
                    "text_total_ms": 0.0,
                },
            }
            if error:
                payload["error"] = str(error)
            return payload

        record: Dict[str, Any] = {
            "image_path": str(image_path),
            "status": "error",
            "ok": False,
            "result_code": 9001,
            "result_name": "internal_error",
            "result_message": "内部异常",
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
            "errors": [],
        }
        try:
            step_start = time.perf_counter()
            image = load_image(image_path)
            _mark("image_read_ms", step_start)
            if debug_artifacts is not None:
                debug_artifacts["image"] = image
            height, width = image.shape[:2]
            record["width"] = int(width)
            record["height"] = int(height)

            correction_info = {
                "label": 0,
                "confidence": None,
                "status": "disabled",
                "corrected": False,
                "actions": None,
            }
            if self.corrector is not None:
                step_start = time.perf_counter()
                image, correction_info = self.corrector.correct_image(image, verbose=self.correction_verbose)
                _mark("correction_ms", step_start)
                if debug_artifacts is not None:
                    debug_artifacts["image"] = image
                height, width = image.shape[:2]
                record["width"] = int(width)
                record["height"] = int(height)
            record["correction"] = correction_info

            step_start = time.perf_counter()
            sampled_image, resize_scale = resize_long_side(image, self.ocr_det_limit_side_len)
            _mark("full_resize_ms", step_start)
            if debug_artifacts is not None:
                debug_artifacts["sampled_image"] = sampled_image

            record["full_image_preprocess"] = {
                "resize_scale": float(resize_scale),
                "resize_long_side": int(self.ocr_det_limit_side_len),
                "sampled_size": [int(sampled_image.shape[1]), int(sampled_image.shape[0])],
                "ocr_enhance_mode": "windowing",
            }

            step_start = time.perf_counter()
            full_ocr_input = enhance_windowing_gray(sampled_image)
            _mark("full_windowing_ms", step_start)
            if debug_artifacts is not None:
                debug_artifacts["full_ocr_input"] = full_ocr_input

            step_start = time.perf_counter()
            full_ocr_result = infer_roi_ocr(
                self.ocr_backend,
                self.ocr_backend,
                full_ocr_input,
                min_score=self.ocr_min_score,
                text_orientation_corrector=self.ocr_text_corrector,
                text_orientation_verbose=self.ocr_orientation_verbose,
            )
            _mark("full_image_ocr_ms", step_start)
            self._merge_prefixed_ocr_timings(step_timings, "full", full_ocr_result)

            full_items_original = self._scale_ocr_items_to_original(full_ocr_result.get("all_items") or [], resize_scale)
            full_plate_vis_items = self._build_plate_visualization_items(full_items_original, source="full_image")
            full_ocr_result = dict(full_ocr_result)
            full_ocr_result["all_items_original"] = full_items_original
            full_ocr_result["items_original"] = [item for item in full_items_original if self._is_usable_ocr_item(item)]

            step_start = time.perf_counter()
            general_fields = extract_general_fields_from_ocr_items(full_items_original)
            _mark("general_field_match_ms", step_start)

            step_start = time.perf_counter()
            full_plate_result = infer_plate_from_ocr_items(
                full_items_original,
                require_jb=True,
                allowed_numbers=self.ocr_allowed_numbers,
            )
            _mark("full_marker_match_ms", step_start)
            full_plate_result = dict(full_plate_result)
            full_plate_result["raw_text_items"] = full_plate_vis_items

            warnings: List[str] = []
            if full_ocr_result.get("item_errors"):
                warnings.append("全图OCR存在部分文本框识别异常")
            if full_plate_result.get("corrections"):
                warnings.append("全图 OCR 标识解析触发了规则纠错")

            field_statistics = dict(general_fields.get("field_statistics") or {})
            field_statistics["full_image_marker_found"] = bool(full_plate_result.get("ok"))
            field_statistics["roi_marker_found"] = False
            field_statistics["iqi_marker_found"] = bool(full_plate_result.get("ok"))

            record["ocr"] = full_ocr_result
            record["full_image_ocr"] = full_ocr_result
            record["full_image_plate"] = full_plate_result
            record["fields"] = general_fields.get("fields") or record["fields"]
            record["field_statistics"] = field_statistics
            record["general_fields_found"] = bool(field_statistics.get("general_fields_found", False))

            roi_info: Dict[str, Any] = {}
            roi_image = None
            roi_gray = None
            roi_ocr_result: Optional[Dict[str, Any]] = None
            roi_plate_result: Optional[Dict[str, Any]] = None
            roi_plate_vis_items: List[Dict[str, Any]] = []
            roi_error_code: Optional[int] = None
            roi_error_message: Optional[str] = None

            step_start = time.perf_counter()
            yolo_result = self.gauge_model.predict(
                source=sampled_image,
                conf=self.gauge_conf,
                iou=self.gauge_iou,
                imgsz=self.gauge_imgsz,
                device=self.gauge_device,
                verbose=False,
            )
            _mark("roi_detect_ms", step_start)

            if not yolo_result:
                roi_error_code = 1101
                roi_error_message = "未检测到像质计 ROI"
                roi_ocr_result = _build_skipped_ocr("skipped_no_roi", roi_error_message)
            else:
                roi_info_resized = extract_best_obb(yolo_result[0], select=self.gauge_select, class_filter=self.gauge_class)
                if roi_info_resized is None:
                    roi_error_code = 1101
                    roi_error_message = "未检测到像质计 ROI"
                    roi_ocr_result = _build_skipped_ocr("skipped_no_roi", roi_error_message)
                else:
                    roi_info = self._scale_roi_info_to_original(roi_info_resized, resize_scale)
                    step_start = time.perf_counter()
                    polygon = np.array(roi_info["polygon"], dtype=np.float32)
                    roi_cropped, crop_matrix = crop_rotated_polygon(image, polygon)
                    _mark("roi_crop_ms", step_start)
                    if roi_cropped is None or crop_matrix is None:
                        roi_error_code = 1102
                        roi_error_message = "像质计 ROI 透视展开失败"
                        roi_ocr_result = _build_skipped_ocr("skipped_roi_invalid", roi_error_message)
                    else:
                        step_start = time.perf_counter()
                        pre_rotate_size = [int(roi_cropped.shape[1]), int(roi_cropped.shape[0])]
                        crop_inverse_matrix = invert_perspective_matrix(crop_matrix)
                        roi_image, rotated, rotation = rotate_if_wide(roi_cropped, enable=self.rotate_roi)
                        if self.enhance_mode == "windowing":
                            roi_window_start = time.perf_counter()
                            roi_gray = enhance_windowing_gray(roi_image)
                            _mark("roi_windowing_ms", roi_window_start)
                        else:
                            roi_gray = to_gray(roi_image)
                            if debug_timer:
                                step_timings.setdefault("roi_windowing_ms", 0.0)
                        _mark("roi_preprocess_ms", step_start)
                        if debug_artifacts is not None:
                            debug_artifacts["roi_image"] = roi_image
                            debug_artifacts["roi_gray"] = roi_gray

                        step_start = time.perf_counter()
                        roi_ocr_result = infer_roi_ocr(
                            self.ocr_backend,
                            self.ocr_backend,
                            roi_gray,
                            min_score=self.ocr_min_score,
                            text_orientation_corrector=self.ocr_text_corrector,
                            text_orientation_verbose=self.ocr_orientation_verbose,
                        )
                        _mark("roi_ocr_ms", step_start)
                        self._merge_prefixed_ocr_timings(step_timings, "roi", roi_ocr_result)

                        step_start = time.perf_counter()
                        roi_plate_result = infer_plate_from_ocr_items(
                            roi_ocr_result.get("all_items") or [],
                            require_jb=True,
                            allowed_numbers=self.ocr_allowed_numbers,
                        )
                        _mark("roi_marker_match_ms", step_start)
                        roi_projected_items = self._project_ocr_items_to_image(
                            roi_ocr_result.get("all_items") or [],
                            crop_inverse_matrix=crop_inverse_matrix,
                            pre_rotate_size=pre_rotate_size,
                            rotated=bool(rotated),
                        )
                        roi_plate_vis_items = self._build_plate_visualization_items(roi_projected_items, source="roi")
                        roi_ocr_result = dict(roi_ocr_result)
                        roi_ocr_result["all_items_image"] = roi_projected_items
                        roi_ocr_result["items_image"] = [item for item in roi_projected_items if self._is_usable_ocr_item(item)]
                        if roi_plate_result is not None:
                            roi_plate_result = dict(roi_plate_result)
                            roi_plate_result["raw_text_items"] = roi_plate_vis_items

                        if roi_ocr_result.get("item_errors"):
                            warnings.append("ROI OCR存在部分文本框识别异常")
                        if roi_plate_result.get("corrections"):
                            warnings.append("ROI OCR 标识解析触发了规则纠错")

                        record["preprocess"] = {
                            "rotation": int(rotation),
                            "rotated": bool(rotated),
                            "enhance_mode": self.enhance_mode,
                            "roi_size": [int(roi_image.shape[1]), int(roi_image.shape[0])],
                        }
                        record["roi"] = {
                            **roi_info,
                            "crop_size_before_rotate": pre_rotate_size,
                            "crop_inverse_matrix": crop_inverse_matrix.tolist(),
                        }

            if not roi_info:
                record["roi"] = {}
            if roi_ocr_result is not None:
                record["roi_ocr"] = roi_ocr_result
            if roi_plate_result is not None:
                record["roi_plate"] = roi_plate_result

            selected_plate: Dict[str, Any]
            plate_source: Optional[str] = None
            if roi_plate_result is not None and roi_plate_result.get("ok"):
                selected_plate = roi_plate_result
                plate_source = "roi"
                if full_plate_result.get("ok") and full_plate_result.get("plate_code") != roi_plate_result.get("plate_code"):
                    warnings.append("全图 OCR 与 ROI OCR 标识不一致，已按 ROI OCR 结果输出")
            elif full_plate_result.get("ok"):
                selected_plate = full_plate_result
                plate_source = "full_image"
                if roi_plate_result is not None and not roi_plate_result.get("ok"):
                    warnings.append("ROI OCR 未识别出像质计标识，已回退到全图 OCR 结果")
            elif roi_plate_result is not None:
                selected_plate = roi_plate_result
            else:
                selected_plate = full_plate_result

            field_statistics["roi_marker_found"] = bool(roi_plate_result and roi_plate_result.get("ok"))
            field_statistics["iqi_marker_found"] = bool(selected_plate.get("ok"))
            record["field_statistics"] = field_statistics
            record["general_fields_found"] = bool(field_statistics.get("general_fields_found", False))
            record["iqi_marker_found"] = bool(selected_plate.get("ok"))
            selected_plate = dict(selected_plate)
            if plate_source == "roi":
                selected_plate["raw_text_items"] = roi_plate_vis_items
            elif plate_source == "full_image":
                selected_plate["raw_text_items"] = full_plate_vis_items
            else:
                selected_plate.setdefault("raw_text_items", [])
            record["plate"] = selected_plate
            record["plate_source"] = plate_source

            if roi_error_code is not None:
                record["wire"] = self._build_skipped_wire(
                    "skipped_no_roi" if roi_error_code == 1101 else "skipped_roi_invalid",
                    roi_error_message,
                )
                error_entries = [{"stage": "roi", **build_result_status(roi_error_code, roi_error_message)}]
                self._attach_visualization_payload(
                    record,
                    roi_plate_vis_items=roi_plate_vis_items,
                    full_plate_vis_items=full_plate_vis_items,
                )
                final_record = self._finalize_record(record, error_entries, warnings)
                _attach_timing(final_record)
                return final_record, debug_artifacts

            if self.fclip_inferencer is not None:
                step_start = time.perf_counter()
                wire_result = self.fclip_inferencer.infer(
                    roi_gray,
                    crop_inverse_matrix=np.array(record["roi"].get("crop_inverse_matrix"), dtype=np.float32),
                    pre_rotate_size=record["roi"].get("crop_size_before_rotate"),
                    rotated=bool(record.get("preprocess", {}).get("rotated", False)),
                )
                _mark("wire_infer_ms", step_start)
            else:
                wire_result = {
                    "status": "error",
                    "error": "FClip is disabled because no checkpoint was provided.",
                    "wire_count": None,
                    "parsed_line_count": 0,
                    "lines": [],
                    "warnings": [],
                }

            warnings.extend(wire_result.get("warnings") or [])
            record["wire"] = wire_result

            wire_error_entries: List[Dict[str, Any]] = []
            if wire_result.get("status") != "ok":
                wire_error_entries.append({"stage": "wire", **build_result_status(3001, wire_result.get("error") or "像质丝识别失败")})
            elif wire_result.get("wire_count") is None:
                wire_error_entries.append({"stage": "wire", **build_result_status(3002)})

            if not selected_plate.get("ok"):
                error_entries = list(wire_error_entries)
                error_entries.append({"stage": "marker", **build_result_status(int(selected_plate.get("result_code", 9001)))})
                self._attach_visualization_payload(
                    record,
                    roi_plate_vis_items=roi_plate_vis_items,
                    full_plate_vis_items=full_plate_vis_items,
                )
                final_record = self._finalize_record(record, error_entries, warnings)
                _attach_timing(final_record)
                return final_record, debug_artifacts

            step_start = time.perf_counter()
            grade_result = compute_iqi_grade(
                selected_plate.get("iqi_type"),
                selected_plate.get("number"),
                wire_result.get("wire_count"),
                allowed_numbers=self.ocr_allowed_numbers,
            )
            _mark("grade_fusion_ms", step_start)
            record["grade_rule"] = grade_result
            error_entries = list(wire_error_entries)
            if selected_plate.get("ok") and wire_result.get("status") == "ok" and not grade_result.get("ok"):
                error_entries.append({"stage": "grade", **build_result_status(int(grade_result.get("result_code", 9001)))})

            final_record = self._finalize_record(record, error_entries, warnings, grade=grade_result.get("grade"))
            final_record["plate_source"] = plate_source
            self._attach_visualization_payload(
                final_record,
                roi_plate_vis_items=roi_plate_vis_items,
                full_plate_vis_items=full_plate_vis_items,
            )
            _attach_timing(final_record)
            return final_record, debug_artifacts
        except FileNotFoundError as exc:
            record.update(build_result_status(1001, str(exc)))
            record["errors"] = [{"stage": "image", **build_result_status(1001, str(exc))}]
            _attach_timing(record)
            return record, debug_artifacts
        except Exception as exc:
            record.update(build_result_status(9001, str(exc)))
            record["errors"] = [{"stage": "pipeline", **build_result_status(9001, str(exc))}]
            _attach_timing(record)
            return record, debug_artifacts


def build_wire_vis_image(roi_image: np.ndarray, wire_result: Dict[str, Any]) -> np.ndarray:
    vis = roi_image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    for line in wire_result.get("lines") or []:
        points = line.get("roi_xy") or []
        if len(points) != 2:
            continue
        p0 = (int(round(points[0][0])), int(round(points[0][1])))
        p1 = (int(round(points[1][0])), int(round(points[1][1])))
        cv2.line(vis, p0, p1, (0, 0, 255), 2, lineType=cv2.LINE_AA)
    text = f"wire_count={wire_result.get('wire_count')} parsed={wire_result.get('parsed_line_count')}"
    cv2.putText(vis, text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)
    return vis


def build_final_result_vis_image(
    image: np.ndarray,
    visualization: Optional[Dict[str, Any]] = None,
    plate_code: Optional[str] = None,
    grade: Optional[int] = None,
    wire_count: Optional[int] = None,
) -> np.ndarray:
    vis = image.copy()
    if vis.ndim == 2:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
    elif vis.ndim == 3 and vis.shape[2] == 1:
        vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)

    visualization = dict(visualization or {})

    roi_polygon = visualization.get("roi_polygon_xy") or []
    try:
        roi_pts = np.asarray(roi_polygon, dtype=np.float32).reshape(-1, 2)
    except Exception:
        roi_pts = np.zeros((0, 2), dtype=np.float32)
    if roi_pts.shape[0] >= 3:
        cv2.polylines(
            vis,
            [roi_pts.astype(np.int32).reshape(-1, 1, 2)],
            isClosed=True,
            color=(0, 255, 0),
            thickness=3,
            lineType=cv2.LINE_AA,
        )

    plate_text_items = (
        visualization.get("plate_text_items_selected")
        or visualization.get("plate_text_items")
        or []
    )
    for item in plate_text_items:
        box = item.get("box_image_xy") or []
        try:
            pts = np.asarray(box, dtype=np.float32).reshape(-1, 2)
        except Exception:
            continue
        if pts.shape[0] < 3:
            continue
        cv2.polylines(
            vis,
            [pts.astype(np.int32).reshape(-1, 1, 2)],
            isClosed=True,
            color=(0, 215, 255),
            thickness=2,
            lineType=cv2.LINE_AA,
        )
        label = str(item.get("text", "")).strip() or "[empty]"
        score = item.get("score")
        if score is not None:
            label = f"{label} ({float(score):.2f})"
        x = int(np.min(pts[:, 0]))
        y = max(20, int(np.min(pts[:, 1])) - 8)
        cv2.putText(
            vis,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 215, 255),
            2,
            lineType=cv2.LINE_AA,
        )

    for line in visualization.get("wire_lines") or []:
        points = line.get("image_xy") or []
        if len(points) != 2:
            continue
        p0 = (int(round(points[0][0])), int(round(points[0][1])))
        p1 = (int(round(points[1][0])), int(round(points[1][1])))
        cv2.line(vis, p0, p1, (0, 0, 255), 2, lineType=cv2.LINE_AA)

    summary_lines = []
    if plate_code:
        summary_lines.append(f"plate={plate_code}")
    if grade is not None:
        summary_lines.append(f"grade={grade}")
    if wire_count is not None:
        summary_lines.append(f"wire_count={wire_count}")
    if summary_lines:
        cv2.putText(
            vis,
            "  ".join(summary_lines),
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2,
            lineType=cv2.LINE_AA,
        )

    return vis


def save_debug_visualizations(
    output_dir: Path,
    sample_dir: Path,
    image: np.ndarray,
    full_ocr_result: Dict[str, Any],
    full_ocr_image: Optional[np.ndarray] = None,
    roi_info: Optional[Dict[str, Any]] = None,
    roi_image: Optional[np.ndarray] = None,
    roi_gray: Optional[np.ndarray] = None,
    roi_ocr_result: Optional[Dict[str, Any]] = None,
    wire_result: Optional[Dict[str, Any]] = None,
    visualization: Optional[Dict[str, Any]] = None,
    plate_code: Optional[str] = None,
    grade: Optional[int] = None,
    wire_count: Optional[int] = None,
) -> Dict[str, Any]:
    ensure_dir(sample_dir)

    input_path = sample_dir / "input.png"
    cv2.imwrite(str(input_path), image)

    payload: Dict[str, Any] = {
        "status_vis_dir": str(sample_dir.relative_to(output_dir)),
        "input_vis_path": str(input_path.relative_to(output_dir)),
    }

    full_base = full_ocr_image if full_ocr_image is not None else image
    full_input_path = sample_dir / "full_ocr_input.png"
    cv2.imwrite(str(full_input_path), full_base)
    full_ocr_vis = draw_ocr_on_roi(full_base, full_ocr_result)
    full_ocr_vis_path = sample_dir / "full_ocr_result.png"
    cv2.imwrite(str(full_ocr_vis_path), full_ocr_vis)

    full_item_vis_rows: List[Dict[str, Any]] = []
    full_debug_rows = build_ocr_item_debug_images(full_base, full_ocr_result)
    if full_debug_rows:
        item_dir = sample_dir / "full_ocr_items"
        ensure_dir(item_dir)
        for row in full_debug_rows:
            crop_index = int(row.get("crop_index", len(full_item_vis_rows)))
            crop_path = item_dir / f"crop_{crop_index:03d}.png"
            rec_input_path = item_dir / f"rec_input_{crop_index:03d}.png"
            rec_result_path = item_dir / f"rec_result_{crop_index:03d}.png"
            cv2.imwrite(str(crop_path), row["crop_image"])
            cv2.imwrite(str(rec_input_path), row["rec_input_image"])
            cv2.imwrite(str(rec_result_path), row["rec_result_image"])
            full_item_vis_rows.append(
                {
                    "crop_index": crop_index,
                    "crop_path": str(crop_path.relative_to(output_dir)),
                    "rec_input_path": str(rec_input_path.relative_to(output_dir)),
                    "rec_result_path": str(rec_result_path.relative_to(output_dir)),
                    "text": row.get("text", ""),
                    "score": row.get("score"),
                }
            )

    payload.update(
        {
            "full_ocr_input_path": str(full_input_path.relative_to(output_dir)),
            "full_ocr_vis_path": str(full_ocr_vis_path.relative_to(output_dir)),
            "full_ocr_item_vis": full_item_vis_rows,
            "ocr_vis_path": str(full_ocr_vis_path.relative_to(output_dir)),
            "ocr_item_vis": full_item_vis_rows,
        }
    )

    if roi_info:
        roi_vis = build_roi_vis_image(image, roi_info)
        roi_vis_path = sample_dir / "ROI.png"
        cv2.imwrite(str(roi_vis_path), roi_vis)
        payload["roi_vis_path"] = str(roi_vis_path.relative_to(output_dir))

    if roi_image is not None:
        roi_image_path = sample_dir / "roi_image.png"
        cv2.imwrite(str(roi_image_path), roi_image)
        payload["roi_image_path"] = str(roi_image_path.relative_to(output_dir))

    if roi_gray is not None:
        roi_gray_path = sample_dir / "roi_gray.png"
        cv2.imwrite(str(roi_gray_path), roi_gray)
        payload["roi_gray_path"] = str(roi_gray_path.relative_to(output_dir))

    if roi_ocr_result is not None and roi_gray is not None:
        roi_ocr_vis = draw_ocr_on_roi(roi_gray, roi_ocr_result)
        roi_ocr_vis_path = sample_dir / "roi_ocr_result.png"
        cv2.imwrite(str(roi_ocr_vis_path), roi_ocr_vis)
        payload["roi_ocr_vis_path"] = str(roi_ocr_vis_path.relative_to(output_dir))

        roi_item_vis_rows: List[Dict[str, Any]] = []
        roi_debug_rows = build_ocr_item_debug_images(roi_gray, roi_ocr_result)
        if roi_debug_rows:
            item_dir = sample_dir / "roi_ocr_items"
            ensure_dir(item_dir)
            for row in roi_debug_rows:
                crop_index = int(row.get("crop_index", len(roi_item_vis_rows)))
                crop_path = item_dir / f"crop_{crop_index:03d}.png"
                rec_input_path = item_dir / f"rec_input_{crop_index:03d}.png"
                rec_result_path = item_dir / f"rec_result_{crop_index:03d}.png"
                cv2.imwrite(str(crop_path), row["crop_image"])
                cv2.imwrite(str(rec_input_path), row["rec_input_image"])
                cv2.imwrite(str(rec_result_path), row["rec_result_image"])
                roi_item_vis_rows.append(
                    {
                        "crop_index": crop_index,
                        "crop_path": str(crop_path.relative_to(output_dir)),
                        "rec_input_path": str(rec_input_path.relative_to(output_dir)),
                        "rec_result_path": str(rec_result_path.relative_to(output_dir)),
                        "text": row.get("text", ""),
                        "score": row.get("score"),
                    }
                )
            payload["roi_ocr_item_vis"] = roi_item_vis_rows

    if wire_result is not None and roi_image is not None:
        wire_vis = build_wire_vis_image(roi_image, wire_result)
        wire_vis_path = sample_dir / "wire_result.png"
        cv2.imwrite(str(wire_vis_path), wire_vis)
        payload["wire_vis_path"] = str(wire_vis_path.relative_to(output_dir))

    if visualization:
        final_result_vis = build_final_result_vis_image(
            image=image,
            visualization=visualization,
            plate_code=plate_code,
            grade=grade,
            wire_count=wire_count,
        )
        final_result_path = sample_dir / "finalresult.png"
        cv2.imwrite(str(final_result_path), final_result_vis)
        payload["final_result_vis_path"] = str(final_result_path.relative_to(output_dir))

    return payload


def build_iqi_statistics(results: Sequence[Dict[str, Any]], topk: int = 200) -> Dict[str, Any]:
    ocr_stats = build_ocr_statistics(list(results), topk=topk)
    grade_counter = Counter()
    type_counter = Counter()
    field_totals = Counter()
    ok_total = 0
    failure_total = 0
    images_with_general_fields = 0
    images_with_iqi_marker = 0

    for record in results:
        if record.get("ok"):
            ok_total += 1
            if record.get("grade") is not None:
                grade_counter[str(int(record["grade"]))] += 1
        else:
            failure_total += 1
        if record.get("iqi_type"):
            type_counter[str(record["iqi_type"])] += 1

        field_stats = record.get("field_statistics") or {}
        if field_stats.get("general_fields_found"):
            images_with_general_fields += 1
        if field_stats.get("iqi_marker_found"):
            images_with_iqi_marker += 1

        fields = record.get("fields") or {}
        field_totals["component_codes"] += len(fields.get("component_codes") or [])
        field_totals["weld_film_pairs"] += len(fields.get("weld_film_pairs") or [])
        field_totals["weld_numbers"] += len(fields.get("weld_numbers") or [])
        field_totals["film_numbers"] += len(fields.get("film_numbers") or [])
        field_totals["pipe_specs"] += len(fields.get("pipe_specs") or [])

    return {
        "images_total": len(results),
        "success_total": int(ok_total),
        "failure_total": int(failure_total),
        "result_code_hist": summarize_result_codes(results),
        "result_code_hist_named": summarize_result_codes_named(results),
        "iqi_type_hist": {key: int(value) for key, value in sorted(type_counter.items())},
        "grade_hist": {key: int(value) for key, value in sorted(grade_counter.items(), key=lambda item: int(item[0]))},
        "field_totals": {key: int(value) for key, value in sorted(field_totals.items())},
        "images_with_general_fields": int(images_with_general_fields),
        "images_with_iqi_marker": int(images_with_iqi_marker),
        "ocr_stats": ocr_stats,
    }


def build_delivery_record(record: Dict[str, Any]) -> Dict[str, Any]:
    visualization = record.get("visualization") or {}
    fields = record.get("fields") or {}
    plate_text_items_selected = []
    for item in visualization.get("plate_text_items_selected") or []:
        plate_text_items_selected.append(
            {
                "text": item.get("text"),
                "score": item.get("score"),
                "box_image_xy": item.get("box_image_xy"),
            }
        )
    payload = {
        "image_path": record.get("image_path"),
        "ok": bool(record.get("ok", False)),
        "result_code": int(record.get("result_code", 9001)),
        "result_name": record.get("result_name"),
        "result_message": record.get("result_message"),
        "grade": record.get("grade"),
        "iqi_type": record.get("iqi_type"),
        "plate_code": record.get("plate_code"),
        "plate_number": record.get("plate_number"),
        "plate_source": record.get("plate_source"),
        "wire_count": record.get("wire_count"),
        "general_fields_found": bool(record.get("general_fields_found", False)),
        "iqi_marker_found": bool(record.get("iqi_marker_found", False)),
        "visualization": {
            "roi_polygon_xy": visualization.get("roi_polygon_xy"),
            "plate_text_items_selected": plate_text_items_selected,
            "wire_lines": visualization.get("wire_lines") or [],
        },
        "fields": {
            "component_codes": fields.get("component_codes") or [],
            "weld_film_pairs": fields.get("weld_film_pairs") or [],
            "weld_numbers": fields.get("weld_numbers") or [],
            "film_numbers": fields.get("film_numbers") or [],
            "pipe_specs": fields.get("pipe_specs") or [],
        },
        "field_statistics": record.get("field_statistics") or {},
        "warnings": record.get("warnings") or [],
        "errors": record.get("errors") or [],
    }
    if record.get("final_result_vis_path"):
        payload["final_result_vis_path"] = record.get("final_result_vis_path")
    if record.get("status_vis_dir"):
        payload["status_vis_dir"] = record.get("status_vis_dir")
    return payload


def collect_input_images(
    image_path: Optional[str] = None,
    image_dir: Optional[str] = None,
    image_list: Optional[str] = None,
    max_images: Optional[int] = None,
) -> List[Path]:
    if image_path:
        paths = [Path(image_path).resolve()]
    else:
        paths = collect_images(
            Path(image_dir).resolve() if image_dir else None,
            Path(image_list).resolve() if image_list else None,
            max_images=max_images,
        )
    if max_images is not None:
        paths = paths[:max_images]
    return paths
