import json
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

fake_fclip_stage = types.ModuleType("gauge.fclip_stage")
fake_fclip_stage.FClipInferencer = object
fake_fclip_stage.invert_perspective_matrix = lambda matrix: matrix
fake_fclip_stage.perspective_transform_points = lambda points, _matrix: points
fake_fclip_stage.undo_ccw90_points = lambda points, pre_rotate_size=None: points
sys.modules.setdefault("gauge.fclip_stage", fake_fclip_stage)

fake_ocr_stage = types.ModuleType("gauge.ocr_stage")
fake_ocr_stage.PaddleOCRSubprocessClient = object
fake_ocr_stage.build_ocr_item_debug_images = lambda *args, **kwargs: {}
fake_ocr_stage.build_ocr_statistics = lambda *args, **kwargs: {}
fake_ocr_stage.draw_ocr_on_roi = lambda *args, **kwargs: None
fake_ocr_stage.infer_roi_ocr = lambda *args, **kwargs: {}
sys.modules.setdefault("gauge.ocr_stage", fake_ocr_stage)

from gauge.iqi_inferencer import build_delivery_record
import run_iqi_grade_infer


class BuildDeliveryRecordTest(unittest.TestCase):
    def test_delivery_record_uses_visualization_payload(self) -> None:
        record = {
            "image_path": "/tmp/demo.png",
            "ok": True,
            "result_code": 0,
            "result_name": "success",
            "result_message": "识别成功",
            "grade": 11,
            "iqi_type": "general",
            "plate_code": "10FEJB",
            "plate_number": 10,
            "plate_source": "roi",
            "wire_count": 2,
            "general_fields_found": True,
            "iqi_marker_found": True,
            "visualization": {
                "roi_polygon_xy": [[1, 2], [3, 4], [5, 6], [7, 8]],
                "roi_bbox": [1, 2, 7, 8],
                "plate_text_items": [{"text": "X"}],
                "plate_text_items_selected": [
                    {
                        "text": "10FEJ",
                        "score": 0.91,
                        "box_image_xy": [[10, 11], [12, 13], [14, 15], [16, 17]],
                        "bbox_image": [10, 11, 16, 17],
                        "source": "roi",
                    }
                ],
                "wire_lines": [{"index": 0, "image_xy": [[11, 12], [13, 14]]}],
            },
            "final_result_vis_path": "vis/success/demo/finalresult.png",
            "roi": {"polygon": [[0, 0], [1, 1], [2, 2], [3, 3]]},
            "plate": {"raw_texts": ["X", "10FEJ"]},
            "wire": {"status": "ok", "wire_count": 2},
            "fields": {
                "component_codes": [{"value": "4S9"}],
                "weld_film_pairs": [{"weld_no": "66", "film_no": "2Y"}],
                "weld_numbers": [{"value": "66"}],
                "film_numbers": [{"value": "2Y"}],
                "pipe_specs": [{"value": "57X12"}],
            },
            "field_statistics": {"component_code_count": 1},
            "warnings": [],
            "errors": [],
        }

        result = build_delivery_record(record)

        self.assertEqual(
            result["visualization"],
            {
                "roi_polygon_xy": [[1, 2], [3, 4], [5, 6], [7, 8]],
                "plate_text_items_selected": [
                    {
                        "text": "10FEJ",
                        "score": 0.91,
                        "box_image_xy": [[10, 11], [12, 13], [14, 15], [16, 17]],
                    }
                ],
                "wire_lines": [{"index": 0, "image_xy": [[11, 12], [13, 14]]}],
            },
        )
        self.assertEqual(result["final_result_vis_path"], "vis/success/demo/finalresult.png")
        self.assertNotIn("roi", result)
        self.assertNotIn("plate", result)
        self.assertNotIn("wire", result)
        self.assertEqual(result["fields"]["component_codes"][0]["value"], "4S9")


class RunIQIGradeInferMainTest(unittest.TestCase):
    def test_parse_args_accepts_hidden_correction_options_without_showing_in_help(self) -> None:
        with mock.patch(
            "sys.argv",
            [
                "run_iqi_grade_infer.py",
                "--image-path",
                "demo.png",
                "--gauge-weights",
                "models/guagerotation.pt",
                "--fclip-ckpt",
                "models/fclip67.pth.tar",
                "--enable-correction",
                "--correction-model",
                "models/weld_orientation_model.pth",
                "--correction-device",
                "cuda:0",
                "--correction-verbose",
            ],
        ):
            args = run_iqi_grade_infer.parse_args()

        self.assertTrue(args.enable_correction)
        self.assertEqual(args.correction_model, "models/weld_orientation_model.pth")
        self.assertEqual(args.correction_device, "cuda:0")
        self.assertTrue(args.correction_verbose)

        with mock.patch("argparse.ArgumentParser.exit", side_effect=RuntimeError("help")), \
            mock.patch("sys.argv", ["run_iqi_grade_infer.py", "--help"]), \
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            with self.assertRaises(RuntimeError):
                run_iqi_grade_infer.parse_args()
        help_text = stdout.getvalue()
        self.assertNotIn("--enable-correction", help_text)
        self.assertNotIn("--correction-model", help_text)

    def test_main_passes_hidden_correction_options_to_inferencer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_json = tmp_path / "iqi_grade_results.json"
            image_path = tmp_path / "BGD-009.bmp"
            image_path.write_bytes(b"stub")

            args = SimpleNamespace(
                image_path=str(image_path),
                image_dir=None,
                image_list=None,
                max_images=None,
                output_json=str(output_json),
                vis_dir=None,
                gauge_weights="models/guagerotation.pt",
                gauge_conf=0.25,
                gauge_iou=0.45,
                gauge_imgsz=640,
                gauge_device=None,
                gauge_select="conf",
                gauge_class=None,
                fclip_ckpt="models/fclip67.pth.tar",
                fclip_device=None,
                fclip_config="models/fclip_config.yaml",
                fclip_params="params.yaml",
                fclip_threshold=None,
                enhance_mode="windowing",
                no_rotate=False,
                enable_correction=True,
                correction_model="models/weld_orientation_model.pth",
                correction_device="cuda:0",
                correction_verbose=True,
                ocr_device="gpu",
                ocr_det_model_name="PP-OCRv5_server_det",
                ocr_det_model_dir=None,
                ocr_rec_model_name="en_PP-OCRv5_mobile_rec",
                ocr_rec_model_dir="models/OCR_rec_inference_best_accuracy0325",
                ocr_min_score=0.0,
                ocr_det_limit_side_len=960,
                ocr_det_limit_type="max",
                ocr_topk=200,
                ocr_number_range="1-19",
                enable_ocr_orientation=True,
                ocr_orientation_model="models/ocr_orientation_model.pth",
                ocr_orientation_device="cuda:0",
            )

            full_record = {
                "image_path": str(image_path),
                "ok": True,
                "result_code": 0,
                "result_name": "success",
                "result_message": "识别成功",
                "grade": 11,
                "iqi_type": "general",
                "plate_code": "10FEJB",
                "plate_number": 10,
                "plate_source": "roi",
                "wire_count": 2,
                "general_fields_found": True,
                "iqi_marker_found": True,
                "fields": {
                    "component_codes": [],
                    "weld_film_pairs": [],
                    "weld_numbers": [],
                    "film_numbers": [],
                    "pipe_specs": [],
                },
                "field_statistics": {},
                "warnings": [],
                "errors": [],
                "visualization": {},
            }

            inferencer = mock.Mock()
            inferencer.infer_image_path.return_value = (full_record, None)
            inferencer.get_runtime_meta.return_value = {"runtime": "stub"}

            with mock.patch.object(run_iqi_grade_infer, "parse_args", return_value=args), \
                mock.patch.object(run_iqi_grade_infer, "collect_input_images", return_value=[image_path]), \
                mock.patch.object(run_iqi_grade_infer, "IQIInferencer", return_value=inferencer) as cls_mock, \
                mock.patch.object(
                    run_iqi_grade_infer,
                    "build_iqi_statistics",
                    return_value={
                        "images_total": 1,
                        "success_total": 1,
                        "failure_total": 0,
                        "result_code_hist": {"0": 1},
                        "result_code_hist_named": {"success": 1},
                        "iqi_type_hist": {"general": 1},
                        "grade_hist": {"11": 1},
                        "field_totals": {},
                        "images_with_general_fields": 1,
                        "images_with_iqi_marker": 1,
                    },
                ):
                run_iqi_grade_infer.main()

            cls_mock.assert_called_once()
            kwargs = cls_mock.call_args.kwargs
            self.assertTrue(kwargs["enable_correction"])
            self.assertEqual(kwargs["correction_model"], "models/weld_orientation_model.pth")
            self.assertEqual(kwargs["correction_device"], "cuda:0")
            self.assertTrue(kwargs["correction_verbose"])

    def test_main_writes_visualization_fields_into_delivery_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_json = tmp_path / "iqi_grade_results.json"
            vis_dir = tmp_path / "vis"
            image_path = tmp_path / "BGD-009.bmp"
            image_path.write_bytes(b"stub")

            args = SimpleNamespace(
                image_path=str(image_path),
                image_dir=None,
                image_list=None,
                max_images=None,
                output_json=str(output_json),
                vis_dir=str(vis_dir),
                gauge_weights="models/guagerotation.pt",
                gauge_conf=0.25,
                gauge_iou=0.45,
                gauge_imgsz=640,
                gauge_device=None,
                gauge_select="conf",
                gauge_class=None,
                fclip_ckpt="models/fclip67.pth.tar",
                fclip_device=None,
                fclip_config="models/fclip_config.yaml",
                fclip_params="params.yaml",
                fclip_threshold=None,
                enhance_mode="windowing",
                no_rotate=False,
                enable_correction=False,
                correction_model=None,
                correction_device=None,
                correction_verbose=False,
                ocr_device="gpu",
                ocr_det_model_name="PP-OCRv5_server_det",
                ocr_det_model_dir=None,
                ocr_rec_model_name="en_PP-OCRv5_mobile_rec",
                ocr_rec_model_dir="models/OCR_rec_inference_best_accuracy0325",
                ocr_min_score=0.0,
                ocr_det_limit_side_len=960,
                ocr_det_limit_type="max",
                ocr_topk=200,
                ocr_number_range="1-19",
                enable_ocr_orientation=True,
                ocr_orientation_model="models/ocr_orientation_model.pth",
                ocr_orientation_device="cuda:0",
            )

            full_record = {
                "image_path": str(image_path),
                "ok": True,
                "result_code": 0,
                "result_name": "success",
                "result_message": "识别成功",
                "grade": 11,
                "iqi_type": "general",
                "plate_code": "10FEJB",
                "plate_number": 10,
                "plate_source": "roi",
                "wire_count": 2,
                "general_fields_found": True,
                "iqi_marker_found": True,
                "roi": {"polygon": [[1, 2], [3, 4], [5, 6], [7, 8]]},
                "plate": {"raw_texts": ["10FEJ"]},
                "wire": {"status": "ok", "wire_count": 2, "lines": []},
                "visualization": {
                    "roi_polygon_xy": [[1, 2], [3, 4], [5, 6], [7, 8]],
                    "roi_bbox": [1, 2, 7, 8],
                    "plate_text_items": [{"text": "X"}],
                    "plate_text_items_selected": [
                        {
                            "text": "10FEJ",
                            "score": 0.91,
                            "box_image_xy": [[10, 11], [12, 13], [14, 15], [16, 17]],
                            "bbox_image": [10, 11, 16, 17],
                            "source": "roi",
                        }
                    ],
                    "wire_lines": [{"index": 0, "image_xy": [[11, 12], [13, 14]]}],
                },
                "fields": {
                    "component_codes": [],
                    "weld_film_pairs": [],
                    "weld_numbers": [],
                    "film_numbers": [],
                    "pipe_specs": [],
                },
                "field_statistics": {},
                "warnings": [],
                "errors": [],
            }
            artifacts = {
                "image": np.zeros((16, 16, 3), dtype=np.uint8),
                "full_ocr_input": np.zeros((16, 16, 3), dtype=np.uint8),
                "roi_image": np.zeros((8, 8, 3), dtype=np.uint8),
                "roi_gray": np.zeros((8, 8), dtype=np.uint8),
            }

            inferencer = mock.Mock()
            inferencer.infer_image_path.return_value = (full_record, artifacts)
            inferencer.get_runtime_meta.return_value = {"runtime": "stub"}

            with mock.patch.object(run_iqi_grade_infer, "parse_args", return_value=args), \
                mock.patch.object(run_iqi_grade_infer, "collect_input_images", return_value=[image_path]), \
                mock.patch.object(run_iqi_grade_infer, "IQIInferencer", return_value=inferencer), \
                mock.patch.object(
                    run_iqi_grade_infer,
                    "save_debug_visualizations",
                    return_value={"final_result_vis_path": "vis/success/BGD-009/finalresult.png"},
                ), \
                mock.patch.object(
                    run_iqi_grade_infer,
                    "build_iqi_statistics",
                    return_value={
                        "images_total": 1,
                        "success_total": 1,
                        "failure_total": 0,
                        "result_code_hist": {"0": 1},
                        "result_code_hist_named": {"success": 1},
                        "iqi_type_hist": {"general": 1},
                        "grade_hist": {"11": 1},
                        "field_totals": {},
                        "images_with_general_fields": 1,
                        "images_with_iqi_marker": 1,
                    },
                ):
                run_iqi_grade_infer.main()

            with output_json.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            result = payload["results"][0]
            self.assertEqual(result["visualization"]["plate_text_items_selected"][0]["text"], "10FEJ")
            self.assertEqual(
                set(result["visualization"]["plate_text_items_selected"][0].keys()),
                {"text", "score", "box_image_xy"},
            )
            self.assertNotIn("plate_text_items", result["visualization"])
            self.assertNotIn("roi_bbox", result["visualization"])
            self.assertEqual(result["final_result_vis_path"], "vis/success/BGD-009/finalresult.png")
            self.assertNotIn("roi", result)
            self.assertNotIn("plate", result)
            self.assertNotIn("wire", result)


if __name__ == "__main__":
    unittest.main()
