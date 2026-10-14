import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import cv_io  # noqa: E402


class CvIoUnicodePathTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "中文 目录"
        self.dir.mkdir()
        self.img = (np.random.rand(20, 30, 3) * 255).astype(np.uint8)

    def test_png_roundtrip_in_unicode_dir(self):
        path = self.dir / "图 1.png"
        self.assertTrue(cv_io.imwrite(path, self.img))
        out = cv_io.imread(path, cv2.IMREAD_UNCHANGED)
        self.assertTrue(np.array_equal(out, self.img))

    def test_16bit_preserved(self):
        path = self.dir / "a.tif"
        img16 = self.img.astype(np.uint16) * 200
        self.assertTrue(cv_io.imwrite(path, img16))
        out = cv_io.imread(path, cv2.IMREAD_UNCHANGED)
        self.assertEqual(out.dtype, np.uint16)
        self.assertTrue(np.array_equal(out, img16))

    def test_missing_or_empty_file_returns_none(self):
        self.assertIsNone(cv_io.imread(self.dir / "none.png"))
        empty = self.dir / "empty.png"
        empty.write_bytes(b"")
        self.assertIsNone(cv_io.imread(empty))


if __name__ == "__main__":
    unittest.main()
