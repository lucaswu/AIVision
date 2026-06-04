#!/usr/bin/env python3
"""ROI OCR inference on text-detected crops."""

from __future__ import annotations

import time
from typing import Any, Dict, List

import numpy as np

from gauge.services.ocr.factory import _ensure_rgb
from gauge.services.ocr.normalize import (
    _filter_items_with_jb,
    normalize_text_det_output,
    normalize_text_rec_output,
)
from gauge.imaging.preprocess import crop_rotated_polygon
from gauge.models.ocr import OCRItem, OCRResult, OCRTimings, OrientationInfo


def _run_ocr_predict(ocr_engine, image: Any) -> Any:
    try:
        return ocr_engine.predict(input=image)
    except TypeError:
        pass

    try:
        return ocr_engine.predict(image)
    except Exception:
        pass

    return ocr_engine.ocr(image, cls=False)


def _run_text_det_predict(text_detector, image: Any) -> Any:
    if hasattr(text_detector, "detect"):
        return text_detector.detect(image)
    try:
        return text_detector.predict(input=image)
    except TypeError:
        return text_detector.predict(image)


def _run_text_rec_predict(text_recognizer, image: Any) -> Any:
    if hasattr(text_recognizer, "recognize"):
        return text_recognizer.recognize(image)
    try:
        return text_recognizer.predict(input=image)
    except TypeError:
        return text_recognizer.predict(image)


def infer_roi_ocr(
    text_detector,
    text_recognizer,
    roi_image: Any,
    min_score: float = 0.0,
    text_orientation_corrector=None,
    text_orientation_verbose: bool = False,
) -> Dict[str, Any]:
    """Run OCR on an image via text detection, per-crop correction and text recognition."""
    pipeline_start = time.perf_counter()
    det_ms = 0.0
    orientation_ms = 0.0
    rec_ms = 0.0

    try:
        det_input = _ensure_rgb(roi_image)
        det_start = time.perf_counter()
        det_raw_output = _run_text_det_predict(text_detector, det_input)
        det_ms = (time.perf_counter() - det_start) * 1000.0
        det_output = normalize_text_det_output(det_raw_output)
        dt_polys = det_output.get("dt_polys", [])
        dt_scores = det_output.get("dt_scores", [])
        if not dt_polys:
            return OCRResult(
                status="no_text",
                det_box_count=0,
                rec_item_count=0,
                timings_ms=OCRTimings(),
            ).model_dump()

        all_items: List[Dict[str, Any]] = []
        item_errors: List[Dict[str, Any]] = []
        success_count = 0

        for idx, poly in enumerate(dt_polys):
            try:
                poly_np = np.array(poly, dtype=np.float32).reshape(-1, 2)
                crop, _ = crop_rotated_polygon(roi_image, poly_np)
                if crop is None:
                    continue

                orientation_info = {
                    "label": None,
                    "confidence": None,
                    "status": "disabled" if text_orientation_corrector is None else "unknown",
                    "corrected": False,
                    "actions": None,
                }
                rec_image = crop.copy()
                if text_orientation_corrector is not None:
                    orientation_start = time.perf_counter()
                    rec_image, orientation_info = text_orientation_corrector.correct_image(
                        crop,
                        verbose=text_orientation_verbose,
                    )
                    orientation_ms += (time.perf_counter() - orientation_start) * 1000.0

                rec_input = _ensure_rgb(rec_image)
                rec_start = time.perf_counter()
                rec_raw_output = _run_text_rec_predict(text_recognizer, rec_input)
                rec_ms += (time.perf_counter() - rec_start) * 1000.0
                rec_output = normalize_text_rec_output(rec_raw_output)
                text = rec_output.get("rec_text", "")
                score = rec_output.get("rec_score")
                accepted_by_score = score is None or score >= min_score
                item_status = "ok"
                if not text:
                    item_status = "empty"
                elif not accepted_by_score:
                    item_status = "low_score"
                success_count += 1
                all_items.append(
                    OCRItem(
                        crop_index=idx,
                        text=text,
                        score=score,
                        box=poly_np.tolist(),
                        det_score=float(dt_scores[idx]) if idx < len(dt_scores) and dt_scores[idx] is not None else None,
                        crop_size=[int(crop.shape[1]), int(crop.shape[0])],
                        status=item_status,
                        accepted_by_score=bool(accepted_by_score),
                        orientation=orientation_info,
                    ).model_dump()
                )
            except Exception as exc:
                item_errors.append({"crop_index": idx, "error": str(exc)})
                all_items.append(
                    OCRItem(
                        crop_index=idx,
                        text="",
                        score=None,
                        box=np.array(poly, dtype=np.float32).reshape(-1, 2).tolist(),
                        det_score=float(dt_scores[idx]) if idx < len(dt_scores) and dt_scores[idx] is not None else None,
                        status="error",
                        accepted_by_score=False,
                        error=str(exc),
                        orientation=OrientationInfo(status="error"),
                    ).model_dump()
                )

        scored_items = [item for item in all_items if item.get("accepted_by_score")]
        jb_items = _filter_items_with_jb(scored_items)
        texts = [str(item.get("text", "")) for item in scored_items]
        scores = [item.get("score") for item in scored_items]
        all_texts = [str(item.get("text", "")) for item in all_items if item.get("text")]

        if scored_items:
            status = "ok"
        elif success_count == 0 and item_errors:
            status = "error"
        else:
            status = "no_text_after_score"

        return OCRResult(
            status=status,
            texts=texts,
            scores=scores,
            items=scored_items,
            all_items=all_items,
            num_items=len(scored_items),
            selected_variant="det_rec",
            all_texts_original=all_texts,
            det_box_count=len(dt_polys),
            rec_item_count=len(all_items),
            jb_items=jb_items,
            jb_texts=[str(item.get("text", "")) for item in jb_items],
            jb_item_count=len(jb_items),
            item_errors=item_errors,
            timings_ms=OCRTimings(
                text_det_ms=round(float(det_ms), 3),
                text_orientation_ms=round(float(orientation_ms), 3),
                text_rec_ms=round(float(rec_ms), 3),
                text_total_ms=round(float(det_ms + orientation_ms + rec_ms), 3),
            ),
        ).model_dump()
    except Exception as exc:
        return OCRResult(
            status="error",
            error=str(exc),
            det_box_count=0,
            rec_item_count=0,
            item_errors=[{"crop_index": None, "error": str(exc)}],
            timings_ms=OCRTimings(),
        ).model_dump()
