import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gauge.iqi_rules import compute_iqi_grade, infer_plate_from_texts


class IQIRulesContractTest(unittest.TestCase):
    def test_infer_plate_from_texts_uses_number_then_material_as_general(self) -> None:
        result = infer_plate_from_texts(["10FEJB"], require_jb=True, allowed_numbers=range(1, 20))

        self.assertTrue(result["ok"])
        self.assertEqual(result["iqi_type"], "general")
        self.assertEqual(result["number"], 10)
        self.assertEqual(result["plate_code"], "10FEJB")

    def test_infer_plate_from_texts_uses_material_then_number_as_special(self) -> None:
        result = infer_plate_from_texts(["FE10JB"], require_jb=True, allowed_numbers=range(1, 20))

        self.assertTrue(result["ok"])
        self.assertEqual(result["iqi_type"], "special")
        self.assertEqual(result["number"], 10)
        self.assertEqual(result["plate_code"], "FE10JB")
        self.assertEqual(result["candidate_codes"], ["FE10JB"])

    def test_infer_plate_from_texts_normalizes_ocr_digit_aliases(self) -> None:
        general = infer_plate_from_texts(["1OFEJB"], require_jb=True, allowed_numbers=range(1, 20))
        special = infer_plate_from_texts(["FE1OJB"], require_jb=True, allowed_numbers=range(1, 20))

        self.assertTrue(general["ok"])
        self.assertEqual(general["iqi_type"], "general")
        self.assertEqual(general["number"], 10)
        self.assertEqual(general["plate_code"], "10FEJB")
        self.assertIn("O@1->0", general["corrections"])

        self.assertTrue(special["ok"])
        self.assertEqual(special["iqi_type"], "special")
        self.assertEqual(special["number"], 10)
        self.assertEqual(special["plate_code"], "FE10JB")
        self.assertIn("O@1->0", special["corrections"])

    def test_compute_iqi_grade_special_accepts_single_visible_wire(self) -> None:
        result = compute_iqi_grade("special", 10, 1, allowed_numbers=range(1, 20))

        self.assertTrue(result["ok"])
        self.assertEqual(result["grade"], 10)
        self.assertEqual(result["wire_count"], 1)

    def test_compute_iqi_grade_general_counts_from_start_number(self) -> None:
        result = compute_iqi_grade("general", 10, 3, allowed_numbers=range(1, 20))

        self.assertTrue(result["ok"])
        self.assertEqual(result["grade"], 12)
        self.assertEqual(result["wire_count"], 3)

    def test_compute_iqi_grade_general_rejects_non_standard_start_number(self) -> None:
        result = compute_iqi_grade("general", 2, 3, allowed_numbers=range(1, 20))

        self.assertFalse(result["ok"])
        self.assertEqual(result["result_code"], 2007)


if __name__ == "__main__":
    unittest.main()
