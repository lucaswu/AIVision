#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weld OCR Runner Utility

This module provides OCR functionality integrated into the weld inference pipeline.

Processes in-memory BGR images (corrected image C) and produces outputs
fully compatible with OCR_main.py / BatchOCRProcessor:
    - Same per-image result dict format
    - Same statistics CSV (ocr_statistics.csv)
    - Same detailed JSON (ocr_detailed_results.json)
    - Same simplified results JSON (ocr_results.json)

OCR utility functions are loaded via importlib from:
    model/OCR/utils/ocr_utils.py
"""

import os
import json
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# Default OCR utils path relative to the weld module root (model/weld/)
_MODULE_DIR = Path(__file__).resolve().parent          # model/weld/utils/
_WELD_ROOT  = _MODULE_DIR.parent                       # model/weld/
_DEFAULT_OCR_UTILS_PATH = _WELD_ROOT.parent / "OCR" / "utils" / "ocr_utils.py"

# Module-level availability flag (set on first successful load)
_OCR_UTILS_AVAILABLE = _DEFAULT_OCR_UTILS_PATH.exists()


class OCRRunner:
    """
    Lightweight PaddleOCR runner integrated into the weld inference pipeline.

    Processes in-memory BGR images (corrected image C) and produces outputs
    fully compatible with OCR_main.py / BatchOCRProcessor:
        - Same per-image result dict format
        - Same statistics CSV (ocr_statistics.csv)
        - Same detailed JSON (ocr_detailed_results.json)
        - Same simplified results JSON (ocr_results.json)

    OCR utility functions (classify_text, draw_annotations, etc.) are loaded
    lazily from the OCR utils module on first use.
    """

    def __init__(self,
                 max_image_size: int = 1920,
                 save_annotations: bool = True,
                 verbose: bool = False,
                 ocr_utils_path: Optional[Union[str, Path]] = None):
        """
        Initialize the OCR runner.

        Args:
            max_image_size: Maximum image edge length before downscaling.
            save_annotations: Whether to save annotated output images.
            verbose: Print per-image OCR details.
            ocr_utils_path: Explicit path to ocr_utils.py.
                If None, the module will search relative to the weld root.
        """
        self.max_image_size = max_image_size
        self.save_annotations = save_annotations
        self.verbose = verbose
        self.statistics: List[Dict] = []
        self.results: List[Dict] = []

        self._ocr = None

        # Load OCR utility functions
        self._ocr_utils_available, \
        self._classify_text, \
        self._draw_annotations, \
        self._extract_field_statistics, \
        self._print_classification_results = self._load_ocr_utils(ocr_utils_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_ocr_utils(self, filepath: Optional[Union[str, Path]] = None):
        """
        Load OCR utility functions from ocr_utils.py.

        Search order:
          1. ``filepath`` (if provided)
          2. model/OCR/utils/ocr_utils.py (sibling of model/weld/)
          3. current working directory

        Returns:
            Tuple of (available, classify_text, draw_annotations,
                      extract_field_statistics, print_classification_results).
            If loading fails, available=False and all functions are None.
        """
        search_paths: List[Path] = []
        if filepath:
            search_paths.append(Path(filepath))
        search_paths.append(_DEFAULT_OCR_UTILS_PATH)
        search_paths.append(Path(os.getcwd()) / "OCR" / "utils" / "ocr_utils.py")

        for path in search_paths:
            if path.exists():
                try:
                    spec = importlib.util.spec_from_file_location("ocr_utils", str(path))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    print(f"[OCRRunner] 工具模块已加载: {path}")
                    return (
                        True,
                        module.classify_text,
                        module.draw_annotations,
                        module.extract_field_statistics,
                        module.print_classification_results,
                    )
                except Exception as exc:
                    print(f"[OCRRunner] 警告: 无法加载 OCR 工具 ({path}): {exc}")

        print(f"[OCRRunner] 警告: ocr_utils.py 未找到，OCR 功能不可用。"
              f"已搜索路径: {[str(p) for p in search_paths]}")
        return False, None, None, None, None

    def _init_ocr(self):
        """Lazily initialize PaddleOCR engine (GPU-aware)."""
        if self._ocr is not None:
            return
        from paddleocr import PaddleOCR  # lazy import
        use_gpu = os.environ.get('USE_GPU', 'true').lower() == 'true'
        if use_gpu:
            try:
                import paddle
                if not paddle.device.is_compiled_with_cuda() or paddle.device.cuda.device_count() == 0:
                    print("警告: PaddlePaddle GPU不可用，回退到CPU")
                    use_gpu = False
            except Exception as _e:
                print(f"警告: GPU检测失败 ({_e})，回退到CPU")
                use_gpu = False
        print(f"初始化PaddleOCR (设备: {'GPU' if use_gpu else 'CPU'})...")

        self._ocr = PaddleOCR(
            use_gpu=use_gpu,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Returns True if OCR utility functions were successfully loaded."""
        return self._ocr_utils_available

    def process_image_array(self,
                            img_bgr: Any,
                            image_name: str,
                            save_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Process a BGR numpy array (corrected image C) with OCR.

        Returns a result dict compatible with OCR_main.BatchOCRProcessor.process_single_image().
        Does NOT mutate self.results / self.statistics — caller controls that.

        Args:
            img_bgr: Input image as BGR numpy array.
            image_name: Image identifier used in result dict and log messages.
            save_path: Optional file path to save the annotated output image.

        Returns:
            Result dict with keys: image_path, image_name, recognized_texts,
            classified_results, field_statistics, error. Returns None if OCR
            utils are not available.
        """
        if not self._ocr_utils_available:
            return None

        self._init_ocr()

        try:
            import cv2
            import numpy as np
            from PIL import Image

            # BGR (OpenCV) → RGB → PIL
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)

            # Resize if needed (mirrors process_image_for_ocr logic)
            w, h = pil_img.size
            max_edge = max(w, h)
            if max_edge > self.max_image_size:
                scale = self.max_image_size / max_edge
                pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            else:
                scale = 1.0

            img_array = np.array(pil_img)

            # Run OCR
            ocr_raw = self._ocr.ocr(img_array, cls=True)

            empty_result: Dict[str, Any] = {
                'image_path': image_name,
                'image_name': image_name,
                'recognized_texts': [],
                'classified_results': [],
                'field_statistics': {},
                'error': '未识别到文本',
            }

            if not ocr_raw or not ocr_raw[0]:
                if self.verbose:
                    print(f"  [OCR] {image_name}: 未识别到任何文本")
                return empty_result

            rec_texts = []
            for line in ocr_raw[0]:
                if len(line) >= 2 and len(line[1]) >= 1:
                    rec_texts.append(line[1][0])

            if not rec_texts:
                return empty_result

            if self.verbose:
                print(f"  [OCR] {image_name}: 识别到原始文本: {rec_texts}")

            classified = [self._classify_text(t) for t in rec_texts]
            if self.verbose:
                self._print_classification_results(classified, verbose=True)

            field_stats = self._extract_field_statistics(classified)

            # Save annotated image if requested
            if self.save_annotations and save_path:
                annotated = self._draw_annotations(pil_img, ocr_raw, classified, scale)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                annotated.save(save_path, quality=95)
                if self.verbose:
                    print(f"  [OCR] 标注图片已保存: {save_path}")

            return {
                'image_path': image_name,
                'image_name': image_name,
                'recognized_texts': rec_texts,
                'classified_results': classified,
                'field_statistics': field_stats,
                'error': None,
            }

        except Exception as exc:
            print(f"  [OCR错误] {image_name}: {exc}")
            return {
                'image_path': image_name,
                'image_name': image_name,
                'recognized_texts': [],
                'classified_results': [],
                'field_statistics': {},
                'error': str(exc),
            }

    def _extract_statistics(self, result: Dict) -> Dict:
        """Mirror of BatchOCRProcessor._extract_statistics()."""
        weld_no_list: List[str] = []
        film_no_list: List[str] = []
        outer_diameter_list: List[str] = []
        wall_thickness_list: List[str] = []

        for classification in result.get('classified_results', []):
            for field in classification.get('匹配字段', []):
                ft = field.get('字段类型')
                if ft == '焊道号_片号':
                    wn = field.get('焊道号')
                    fn = field.get('片号')
                    if wn:
                        weld_no_list.append(str(wn))
                    if fn:
                        film_no_list.append(str(fn))
                elif ft == '管道规格':
                    outer = field.get('外径')
                    thick = field.get('壁厚')
                    if outer:
                        outer_diameter_list.append(str(outer))
                    if thick:
                        wall_thickness_list.append(str(thick))

        is_complete = all([
            len(result['field_statistics'].get('检测部件代号', [])) > 0,
            len(result['field_statistics'].get('焊道号_片号', [])) > 0,
            len(result['field_statistics'].get('像质计灵敏度', [])) > 0,
            len(result['field_statistics'].get('管道规格', [])) > 0,
        ])

        return {
            '图片名称': result['image_name'],
            '识别文本数': len(result['recognized_texts']),
            '检测部件代号': len(result['field_statistics'].get('检测部件代号', [])),
            '焊道号_片号': len(result['field_statistics'].get('焊道号_片号', [])),
            '像质计灵敏度': len(result['field_statistics'].get('像质计灵敏度', [])),
            '管道规格': len(result['field_statistics'].get('管道规格', [])),
            '未分类数': sum(1 for c in result['classified_results'] if c.get('字段类型') == '未分类'),
            '完全识别': '是' if is_complete else '否',
            '检测部件代号_内容': ', '.join(result['field_statistics'].get('检测部件代号', [])) or '无',
            '像质计灵敏度_内容': ', '.join(result['field_statistics'].get('像质计灵敏度', [])) or '无',
            '焊道号_内容': ', '.join(weld_no_list) if weld_no_list else '无',
            '片号_内容': ', '.join(film_no_list) if film_no_list else '无',
            '管道外径_内容': ', '.join(outer_diameter_list) if outer_diameter_list else '无',
            '管道壁厚_内容': ', '.join(wall_thickness_list) if wall_thickness_list else '无',
        }

    def save_statistics(self, output_dir: Path):
        """Save OCR statistics CSV — mirrors BatchOCRProcessor._save_statistics()."""
        if not self.statistics:
            return
        try:
            import pandas as pd
        except ImportError:
            print("[警告] pandas未安装，跳过OCR统计CSV保存")
            return

        csv_path = output_dir / 'ocr_statistics.csv'
        df = pd.DataFrame(self.statistics)
        complete_count = len(df[df['完全识别'] == '是'])
        incomplete_count = len(df[df['完全识别'] == '否'])
        summary = {
            '图片名称': '汇总',
            '识别文本数': df['识别文本数'].sum(),
            '检测部件代号': df['检测部件代号'].sum(),
            '焊道号_片号': df['焊道号_片号'].sum(),
            '像质计灵敏度': df['像质计灵敏度'].sum(),
            '管道规格': df['管道规格'].sum(),
            '未分类数': df['未分类数'].sum(),
            '完全识别': f"是: {complete_count}, 否: {incomplete_count}",
            '检测部件代号_内容': '-', '像质计灵敏度_内容': '-',
            '焊道号_内容': '-', '片号_内容': '-',
            '管道外径_内容': '-', '管道壁厚_内容': '-',
        }
        df = pd.concat([df, pd.DataFrame([summary])], ignore_index=True)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"\nOCR统计结果已保存至: {csv_path}")
        print(f"OCR批量处理汇总: 共处理 {len(self.statistics)} 张, 完全识别 {complete_count} 张")

    def save_detailed_results(self, output_dir: Path):
        """Save detailed OCR JSON — mirrors BatchOCRProcessor._save_detailed_results()."""
        json_path = output_dir / 'ocr_detailed_results.json'
        serializable = []
        for result in self.results:
            sr = {
                'image_name': result['image_name'],
                'image_path': result['image_path'],
                'recognized_texts': result['recognized_texts'],
                'field_statistics': result['field_statistics'],
                'error': result['error'],
                'classified_results': [],
            }
            for classification in result['classified_results']:
                sr['classified_results'].append({
                    '原始文本': classification['原始文本'],
                    '匹配字段': classification.get('匹配字段', []),
                    '字段类型': classification.get('字段类型', ''),
                })
            serializable.append(sr)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"OCR详细结果已保存至: {json_path}")

    def save_results_json(self, output_dir: Path, filename: str = 'ocr_results.json'):
        """Save simplified OCR results JSON — same format as OCR_main.py main() output."""
        results_path = output_dir / filename
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump({'mode': 'ocr', 'results': self.results}, f, indent=2, ensure_ascii=False)
        print(f"OCR结果JSON: {results_path}")


# ---------------------------------------------------------------------------
# Factory and convenience functions
# ---------------------------------------------------------------------------

def create_ocr_runner(max_image_size: int = 1920,
                      save_annotations: bool = True,
                      verbose: bool = False,
                      ocr_utils_path: Optional[Union[str, Path]] = None) -> OCRRunner:
    """
    Factory function to create an OCRRunner instance.

    Args:
        max_image_size: Maximum image edge length before downscaling.
        save_annotations: Whether to save annotated output images.
        verbose: Print per-image OCR details.
        ocr_utils_path: Explicit path to ocr_utils.py. Uses default if None.

    Returns:
        OCRRunner instance.
    """
    return OCRRunner(
        max_image_size=max_image_size,
        save_annotations=save_annotations,
        verbose=verbose,
        ocr_utils_path=ocr_utils_path,
    )
