import unittest
import sys
import types
from unittest import mock

fake_cv2 = types.ModuleType("cv2")
sys.modules.setdefault("cv2", fake_cv2)

from gauge.region_ocr_api import close_region_ocr_api, init_region_ocr_api


class RegionOCRApiInitTest(unittest.TestCase):
    def tearDown(self) -> None:
        close_region_ocr_api()

    def test_init_accepts_and_forwards_detection_model_dir(self) -> None:
        with mock.patch("gauge.region_ocr_service.PaddleOCRSubprocessClient") as client_cls:
            service = init_region_ocr_api(
                ocr_det_model_dir="models/det",
                ocr_rec_model_dir="models/rec",
                ocr_device="cpu",
                enable_orientation=False,
            )

        self.assertIs(service.ocr_backend, client_cls.return_value)
        client_cls.assert_called_once()
        call_kwargs = client_cls.call_args.kwargs
        self.assertEqual(call_kwargs["det_model_name"], "PP-OCRv5_server_det")
        self.assertTrue(call_kwargs["det_model_dir"].endswith("models/det"))
        self.assertTrue(call_kwargs["rec_model_dir"].endswith("models/rec"))
        self.assertEqual(call_kwargs["device"], "cpu")


if __name__ == "__main__":
    unittest.main()
