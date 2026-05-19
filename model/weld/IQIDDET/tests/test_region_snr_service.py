import unittest

import numpy as np

from gauge.region_snr_service import RegionSNRService


class RegionSNRServiceTest(unittest.TestCase):
    def test_small_region_returns_area_invalid(self) -> None:
        service = RegionSNRService()
        image = np.arange(100, dtype=np.uint8).reshape(10, 10)

        result = service.compute_image(image)

        self.assertFalse(result["ok"])
        self.assertEqual(result["result_code"], 4001)
        self.assertIn("不小于", result["message"])
        self.assertEqual(result["area_pixels"], 100)

    def test_threshold_sized_region_is_not_rejected_by_area_check(self) -> None:
        service = RegionSNRService()
        image = np.arange(20 * 55, dtype=np.uint8).reshape(20, 55)

        result = service.compute_image(image)

        self.assertNotEqual(result["result_code"], 4001)
        self.assertTrue(result["ok"])
        self.assertEqual(result["area_pixels"], 20 * 55)


if __name__ == "__main__":
    unittest.main()
