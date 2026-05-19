import py_compile
import runpy
import sys
import types
import unittest
from pathlib import Path


def _run_root_module(repo_root: Path, module_name: str) -> None:
    module_path = repo_root / f"{module_name}.py"
    before_path = list(sys.path)
    watched_modules = [
        module_name,
        "gauge",
        "gauge.fclip_stage",
        "gauge.ocr_stage",
        "FClip",
        "dataset",
    ]
    before_modules = {name: sys.modules.get(name) for name in watched_modules}
    try:
        if module_name == "run_iqi_grade_infer":
            fake_fclip_stage = types.ModuleType("gauge.fclip_stage")
            fake_fclip_stage.FClipInferencer = object
            fake_fclip_stage.invert_perspective_matrix = lambda matrix: matrix
            fake_fclip_stage.perspective_transform_points = lambda points, _matrix: points
            fake_fclip_stage.undo_ccw90_points = lambda points, pre_rotate_size=None: points
            sys.modules["gauge.fclip_stage"] = fake_fclip_stage

            fake_ocr_stage = types.ModuleType("gauge.ocr_stage")
            fake_ocr_stage.PaddleOCRSubprocessClient = object
            fake_ocr_stage.build_ocr_item_debug_images = lambda *args, **kwargs: {}
            fake_ocr_stage.build_ocr_statistics = lambda *args, **kwargs: {}
            fake_ocr_stage.draw_ocr_on_roi = lambda *args, **kwargs: None
            fake_ocr_stage.infer_roi_ocr = lambda *args, **kwargs: {}
            sys.modules["gauge.ocr_stage"] = fake_ocr_stage

        runpy.run_path(str(module_path), run_name=f"__test_{module_name}__")
    finally:
        sys.path[:] = before_path
        for name, module in before_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class DebugScriptLayoutTest(unittest.TestCase):
    def test_source_packages_live_under_src(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"

        for package_name in ["gauge", "FClip", "dataset"]:
            self.assertTrue((src_dir / package_name).is_dir(), f"missing src package: {package_name}")
            self.assertFalse((repo_root / package_name).exists(), f"root package should be moved: {package_name}")

    def test_root_delivery_entrypoints_bootstrap_src_imports(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        for module_name in ["region_ocr_api", "region_SNR_api", "run_iqi_grade_infer"]:
            _run_root_module(repo_root, module_name)

    def test_debug_scripts_live_under_scripts_debug_and_compile(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        debug_dir = repo_root / "scripts" / "debug"

        moved_scripts = [
            debug_dir / "fclip_valid.py",
            debug_dir / "run_region_ocr_batch.py",
        ]
        for script in moved_scripts:
            self.assertTrue(script.is_file(), f"missing debug script: {script}")
            py_compile.compile(str(script), doraise=True)

        self.assertFalse((repo_root / "fclip_valid.py").exists())
        self.assertFalse((repo_root / "run_region_ocr_batch.py").exists())


if __name__ == "__main__":
    unittest.main()
