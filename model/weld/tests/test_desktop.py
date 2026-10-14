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


if __name__ == "__main__":
    unittest.main()
