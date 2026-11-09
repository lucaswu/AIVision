import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop import paths  # noqa: E402
from desktop.inputs import collect_inputs  # noqa: E402
from desktop.render import apply_correction_label, draw_result  # noqa: E402


class CollectInputsTest(unittest.TestCase):
    def test_dir_and_file_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "批次 1"
            (root / "sub").mkdir(parents=True)
            for name in ("a.tif", "b.PNG", "sub/c.dcm", "note.txt"):
                (root / name).write_bytes(b"x")
            items = collect_inputs([root, root / "a.tif"])
            self.assertEqual([str(r) for _, r in items], ["a.tif", "b.PNG", str(Path("sub/c.dcm"))])
            flat = collect_inputs([root], recursive=False)
            self.assertEqual([str(r) for _, r in flat], ["a.tif", "b.PNG"])

    def test_supported_exts_match_pipeline(self):
        import re

        src = (paths.APP_DIR / "run_inference_pipeline.py").read_text(encoding="utf-8")
        m = re.search(r"SUPPORTED_IMAGE_EXTS = \(([^)]*)\)", src)
        exts = tuple(re.findall(r"'([^']+)'", m.group(1)))
        self.assertEqual(exts, paths.SUPPORTED_IMAGE_EXTS)


class RenderTest(unittest.TestCase):
    def test_correction_label_geometry(self):
        img = np.zeros((10, 20, 3), np.uint8)
        self.assertEqual(apply_correction_label(img, 1).shape[:2], (20, 10))
        self.assertEqual(apply_correction_label(img, 2).shape[:2], (10, 20))
        self.assertEqual(apply_correction_label(img, 4).shape[:2], (10, 20))

    def test_draw_result_changes_pixels_and_keeps_input(self):
        img = np.zeros((200, 300, 3), np.uint8)
        result = {"rois": [{"bbox": [10, 10, 290, 190],
                            "detections": [{"bbox": [50, 50, 120, 100], "class_name": "裂纹", "confidence": 0.9}]}],
                  "weld_location": [], "defect_position": {}}
        out = draw_result(img, result)
        self.assertEqual(int(img.sum()), 0)
        self.assertGreater(int(out.sum()), 0)


class CompetitionCellsTest(unittest.TestCase):
    def test_competition_cells_format_mm(self):
        from desktop.ui.main_window import competition_cells

        ev = {
            "grade_label": "Ⅳ级",
            "records": [
                {"defect_type": "裂纹", "x_px": 5002, "x_mm": 211.75, "quantity": "37.5"},
                {"defect_type": "未焊透", "x_px": 288, "x_mm": 12.1, "quantity": "359.0"},
            ],
        }
        cells = competition_cells(ev)
        self.assertEqual(cells[0], "Ⅳ级")
        self.assertEqual(cells[1], "裂纹 X=211.75mm 37.5；未焊透 X=12.1mm 359.0")

    def test_competition_cells_fallback_px(self):
        from desktop.ui.main_window import competition_cells

        ev = {
            "grade_label": "Ⅱ级",
            "records": [
                {"defect_type": "圆形缺陷", "x_px": 100, "quantity": "3"},
            ],
        }
        cells = competition_cells(ev)
        self.assertEqual(cells[0], "Ⅱ级")
        self.assertEqual(cells[1], "圆形缺陷 X=100px 3")


class UiSettingsCompatibilityTest(unittest.TestCase):
    def test_plate_root_attributes_present(self):
        from desktop.settings import UiSettings

        s = UiSettings()
        self.assertTrue(hasattr(s, "competition_report_plate_root"))
        self.assertTrue(hasattr(s, "competition_plate_root"))
        self.assertTrue(hasattr(s, "competition_round_scale"))
        self.assertTrue(hasattr(s, "competition_small_pipe_arc_expand"))
        self.assertFalse(s.competition_report_plate_root)
        self.assertEqual(s.competition_plate_root, "drop")

    def test_json_load_backwards_compatibility(self):
        import json
        from desktop.settings import UiSettings
        from unittest.mock import patch

        legacy_json = json.dumps({"competition_report_plate_root": True})
        with patch.object(paths, "settings_path") as mock_path:
            mock_path.return_value.read_text.return_value = legacy_json
            s = UiSettings.load()
            self.assertTrue(s.competition_report_plate_root)
            self.assertEqual(s.competition_plate_root, "report")

        new_json = json.dumps({"competition_plate_root": "report"})
        with patch.object(paths, "settings_path") as mock_path:
            mock_path.return_value.read_text.return_value = new_json
            s = UiSettings.load()
            self.assertTrue(s.competition_report_plate_root)
            self.assertEqual(s.competition_plate_root, "report")


class MainWindowSummaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        from PyQt6.QtWidgets import QApplication

        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def test_summary_update_and_layout(self):
        from desktop.engine import ImageOutcome, RunSummary
        from desktop.ui.main_window import MainWindow

        win = MainWindow()
        self.assertFalse(win.table.horizontalHeader().isSectionHidden(0))
        # Check summary reset state
        self.assertIn("就绪", win.summary_detail_label.text())

        # Simulate outcome
        o = ImageOutcome(
            index=0, total=1, image_path="test.dcm", rel_path="test.dcm", ok=True,
            competition={"grade_label": "Ⅳ级", "records": [{"defect_type": "裂纹"}]}
        )
        win._outcomes[0] = o
        win._total = 1

        summary = RunSummary(
            output_dir="/tmp/out", total=1, succeeded=1, failed=0, cancelled=False,
            elapsed_s=2.5, answers_path="/tmp/out/answers.xlsx",
            submit_response={"success": True, "data": {"mark": 50}}
        )
        win._update_completed_summary(summary)

        text = win.summary_detail_label.text()
        self.assertIn("Ⅳ级: 1", text)
        self.assertIn("裂纹: <b>1</b>", text)
        self.assertIn("50", text)
        self.assertIn("全目录概况", text)
        self.assertIn("总体评定结果", win.summary_box.title())

        # Also test without score
        summary_no_score = RunSummary(
            output_dir="/tmp/out", total=1, succeeded=1, failed=0, cancelled=False,
            elapsed_s=2.5, answers_path="/tmp/out/answers.xlsx",
            submit_response={"success": True, "data": {}}
        )
        win._update_completed_summary(summary_no_score)
        text_no_score = win.summary_detail_label.text()
        self.assertIn("已成功（服务端已接收提交", text_no_score)

        win.close()


if __name__ == "__main__":
    unittest.main()
