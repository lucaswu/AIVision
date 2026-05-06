#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weld inference entry point.

Features:
    1. Batch load weld inspection images from a directory
    2. Run ROI detection to focus on weld seams
    3. Apply RF-DETR segmentation or detection
    4. Map results back to the original image
"""

import argparse
import hashlib
import json
import sys
import os
import ssl
from dataclasses import dataclass

# Globally disable SSL verification for local dev
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# Disable Ultralytics auto-download/sync
os.environ['YOLO_VERBOSE'] = 'False'
from ultralytics import settings
settings.update({'sync': False})

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

DEBUG_STEP = True

from convert.pj.yolo_roi_extractor import WeldROIDetector  # noqa: E402
from utils.pipeline_utils import FontRenderer, load_image  # noqa: E402
from utils import detection_pipeline as rfdet_pipeline  # noqa: E402
from utils.weld_correction import WeldOrientationCorrector  # noqa: E402
from utils.weld_locaiont_0 import WeldSeamLocator, DEFAULT_LOCATION_MODEL_PATH, compute_grayscale_density as compute_grayscale_loc0  # noqa: E402
from utils.weld_locaiont_1 import WeldDefectPositionDetector, DEFAULT_LOCATION1_MODEL_PATH, compute_grayscale_density as compute_grayscale_loc1  # noqa: E402
# IQI Grade Inferencer (replaces legacy OCR runner)
IQIDDET_ROOT = PROJECT_ROOT / "IQIDDET"
if str(IQIDDET_ROOT) not in sys.path:
    sys.path.insert(0, str(IQIDDET_ROOT))
try:
    from gauge.iqi_inferencer import (  # noqa: E402
        IQIInferencer,
        build_delivery_record,
        build_iqi_statistics,
        save_debug_visualizations,
    )
    _IQI_AVAILABLE = True
except ImportError as _iqi_err:
    _IQI_AVAILABLE = False
    print(f"[警告] IQIInferencer 加载失败，IQI 功能不可用: {_iqi_err}")

try:
    import pydicom
except ImportError:
    pydicom = None


SUPPORTED_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.dcm', '.dicom', '.dic', '.diconde')
DICOM_EXTS = {'.dcm', '.dicom', '.dic', '.diconde'}
HIGH_BIT_EXTS = {'.png', '.tif', '.tiff'} | DICOM_EXTS

# 矫正 label (0-7) 到前端 CSS transform 的映射
# label 表示图片当前状态，矫正操作是其逆操作
LABEL_TO_FRONTEND_TRANSFORM = {
    0: {"rotation": 0,    "flip": False},  # Normal
    1: {"rotation": -90,  "flip": False},  # 顺时90° → 逆时90°矫正
    2: {"rotation": 180,  "flip": False},  # 倒置180° → 旋转180°矫正
    3: {"rotation": 90,   "flip": False},  # 逆时90° → 顺时90°矫正
    4: {"rotation": 0,    "flip": True},   # 镜像 → 水平翻转矫正
    5: {"rotation": -90,  "flip": True},   # 镜像+顺时90°
    6: {"rotation": 180,  "flip": True},   # 镜像+180°
    7: {"rotation": 90,   "flip": True},   # 镜像+逆时90°
}


@dataclass(frozen=True)
class PreparedImageInput:
    original_path: Path
    processing_path: Path
    converted_to_8bit: bool = False


def _normalize_to_uint8(image: np.ndarray,
                        clip_percent: Optional[Tuple[float, float]] = None,
                        invert: bool = False) -> np.ndarray:
    if image is None:
        raise ValueError("Empty image array")

    arr = image.astype(np.float32)
    if clip_percent is not None:
        low, high = np.percentile(arr, clip_percent)
    else:
        low, high = float(np.min(arr)), float(np.max(arr))

    if high <= low:
        out = np.zeros(arr.shape[:2] if arr.ndim == 3 else arr.shape, dtype=np.uint8)
    else:
        arr = np.clip(arr, low, high)
        arr = (arr - low) / (high - low) * 255.0
        if invert:
            arr = 255.0 - arr
        out = arr.astype(np.uint8)

    if out.ndim == 3 and out.shape[2] == 4:
        out = cv2.cvtColor(out, cv2.COLOR_BGRA2BGR)
    return out


def _read_dicom_for_conversion(path: Path) -> Tuple[np.ndarray, bool]:
    if pydicom is None:
        raise RuntimeError("pydicom 未安装，无法读取 DICOM；请在推理镜像中安装 pydicom")

    ds = pydicom.dcmread(str(path), force=True)
    if not hasattr(ds, "PixelData"):
        raise RuntimeError("DICOM 缺少 PixelData")

    arr = ds.pixel_array
    samples_per_pixel = int(getattr(ds, "SamplesPerPixel", 1) or 1)
    if arr.ndim == 4:
        arr = arr[0]
    if arr.ndim == 3 and samples_per_pixel == 1:
        arr = arr[0]

    arr = arr.astype(np.float32)
    slope = float(getattr(ds, "RescaleSlope", 1.0))
    intercept = float(getattr(ds, "RescaleIntercept", 0.0))
    if samples_per_pixel == 1:
        arr = arr * slope + intercept

    invert = str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1"
    return arr, invert


def _read_image_for_preprocessing(path: Path) -> Tuple[np.ndarray, bool]:
    ext = path.suffix.lower()
    if ext in DICOM_EXTS:
        return _read_dicom_for_conversion(path)

    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"无法读取图像: {path}")

    invert = False
    if image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image, invert


def _needs_8bit_conversion(path: Path, image: np.ndarray) -> bool:
    ext = path.suffix.lower()
    if ext in DICOM_EXTS:
        return True
    if ext not in HIGH_BIT_EXTS:
        return False
    return image.dtype != np.uint8


def _prepare_image_input(image_path: Path, prepared_root: Path) -> PreparedImageInput:
    image, invert = _read_image_for_preprocessing(image_path)
    if not _needs_8bit_conversion(image_path, image):
        return PreparedImageInput(original_path=image_path, processing_path=image_path, converted_to_8bit=False)

    image_8 = _normalize_to_uint8(image, invert=invert)
    prepared_root.mkdir(parents=True, exist_ok=True)
    suffix_hash = hashlib.md5(str(image_path).encode("utf-8")).hexdigest()[:8]
    prepared_path = prepared_root / f"{image_path.stem}__src8__{suffix_hash}.png"

    ok = cv2.imwrite(str(prepared_path), image_8)
    if not ok:
        raise RuntimeError(f"写入预处理 8bit 图像失败: {prepared_path}")

    print(f"[预处理] {image_path.name}: {image_path.suffix.lower()} / {image.dtype} -> 8bit PNG")

    return PreparedImageInput(
        original_path=image_path,
        processing_path=prepared_path,
        converted_to_8bit=True,
    )


def _apply_correction_label(image: np.ndarray, label_idx: int) -> np.ndarray:
    """
    Apply the same orientation-restoration transform implied by correction label.

    This mirrors ``WeldOrientationCorrector._restore_image`` but works for
    raw grayscale / 16-bit arrays as well, so we can compute film density on
    the original high-bit image while keeping coordinates aligned with the
    corrected 8-bit inference image.
    """
    img = image.copy()
    rot_state = label_idx % 4

    if rot_state == 1:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif rot_state == 2:
        img = cv2.rotate(img, cv2.ROTATE_180)
    elif rot_state == 3:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    if label_idx >= 4:
        img = cv2.flip(img, 1)

    return img


def _invert_density_image(image: np.ndarray) -> np.ndarray:
    """
    Invert grayscale polarity while preserving the original value range.

    For MONOCHROME1 DICOM, larger raw values represent brighter display values.
    Film density sampling should follow the same visual polarity as the
    downstream 8-bit display conversion, but without compressing to 8-bit.
    """
    if image is None or image.size == 0:
        return image

    arr = image.astype(np.float32, copy=False)
    img_min = float(np.min(arr))
    img_max = float(np.max(arr))
    return (img_max + img_min) - arr


def _load_density_image(image_path: Path, correction_label: int) -> np.ndarray:
    """
    Load the original source image for film-density measurement.

    Unlike the inference branch, this keeps the native precision (e.g. uint16 /
    float32 DICOM values) and only applies polarity correction plus the same
    orientation correction label so the sampling coordinates still line up with
    weld_location / defect_position outputs.
    """
    image, invert = _read_image_for_preprocessing(image_path)
    if invert:
        image = _invert_density_image(image)
    if correction_label != 0:
        image = _apply_correction_label(image, correction_label)
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="焊缝缺陷推理脚本（支持RF-DETR分割/检测模式）"
    )
    parser.add_argument("--image-dir", help="待推理图像目录（如果提供了 --file-list 则忽略）")
    parser.add_argument("--file-list", help="包含待推理图像绝对路径的文本文件（每行一个路径）")
    parser.add_argument("--output-dir", default="inference_outputs", help="输出目录")
    parser.add_argument("--results-json", default="inference_results.json",
                        help="结果JSON文件名（相对output_dir）")
    parser.add_argument("--mode", choices=["seg", "det"], default="seg",
                        help="推理模式：seg=分割，det=RF-DETR检测")
    parser.add_argument("--max-images", type=int, help="最多处理的图像数")

    # ROI配置
    parser.add_argument("--roi-weights", help="ROI检测权重（seg/det模式必填）")
    parser.add_argument("--roi-conf", type=float, default=0.25, help="ROI检测置信度阈值")
    parser.add_argument("--roi-iou", type=float, default=0.45, help="ROI检测IoU阈值")
    parser.add_argument("--roi-padding", type=float, default=0.1, help="ROI外扩比例")

    # 通用
    parser.add_argument("--enhance-mode", choices=["original", "windowing"],
                        default="windowing", help="图像增强模式")
    parser.add_argument("--font-path", help="可选，指定字体文件以正确显示中文标签")
    parser.add_argument("--font-size", type=int, default=20, help="可视化字体大小")

    # 模型通用参数
    parser.add_argument("--primary-weights", help="主模型权重（seg/det通用）")
    parser.add_argument("--fusion-iou", type=float, default=0.5,
                        help="主干/宽切片NMS融合IoU阈值")

    # 分割模式参数
    parser.add_argument("--primary-conf", type=float, default=0.15, help="主模型置信度阈值")
    parser.add_argument("--device", help="推理设备（如0, cuda:0, cpu）")

    # 检测模式参数(RF-DETR)
    parser.add_argument("--det-device", help="RF-DETR推理设备(如cuda:0, cpu)")
    parser.add_argument("--wide-slice", action="store_true",
                        help="启用横切纵拼推理(seg/det模式),结果与主干一起融合")
    
    # 焊缝底片矫正预处理
    parser.add_argument("--enable-correction", action="store_true",
                        help="启用焊缝底片方向矫正预处理")
    parser.add_argument("--correction-model",
                        default="weight/weld_orientation_model.pth",
                        help="焊缝方向矫正模型路径")
    parser.add_argument("--correction-verbose", action="store_true",
                        help="显示矫正过程详细信息")
    parser.add_argument("--save-corrected-dir",
                        help="可选，将矫正后的图像保存到指定目录")

    # 焊缝位置检测 (B 路径)
    parser.add_argument("--enable-location", action="store_true",
                        help="启用焊缝位置检测（YOLO pose 模型）")
    parser.add_argument("--location-model",
                        default=DEFAULT_LOCATION_MODEL_PATH,
                        help="焊缝位置检测模型路径（默认: weight/location_0.pt）")
    parser.add_argument("--location-conf", type=float, default=0.6,
                        help="焊缝位置检测置信度阈值（默认: 0.6）")
    parser.add_argument("--location-verbose", action="store_true",
                        help="显示位置检测过程详细信息")
    parser.add_argument("--save-location-dir",
                        help="可选，将带关键点标注的可视化图像保存到指定目录")

    # 缺陷位置检测2 (D 路径)
    parser.add_argument("--enable-location2", action="store_true",
                        help="启用缺陷位置检测2（YOLO detection + OCR，使用 location_1.pt）")
    parser.add_argument("--location2-model",
                        default=DEFAULT_LOCATION1_MODEL_PATH,
                        help="缺陷位置检测2模型路径（默认: weight/location_1.pt）")
    parser.add_argument("--location2-conf", type=float, default=0.25,
                        help="缺陷位置检测2置信度阈值（默认: 0.25）")
    parser.add_argument("--location2-verbose", action="store_true",
                        help="显示缺陷位置检测2过程详细信息")
    parser.add_argument("--save-location2-dir",
                        help="可选，将缺陷位置检测2可视化图像保存到指定目录")

    # IQI Grade Inferencer 集成参数（替换旧版 OCR runner）
    parser.add_argument("--enable-iqi", action="store_true",
                        help="启用 IQI 像质计识别（调用 IQIDDET/run_iqi_grade_infer.py 逻辑）")
    parser.add_argument("--iqi-results-json", default="iqi_grade_results.json",
                        help="IQI 结果 JSON 文件名（相对 output_dir）")
    # Gauge（OBB 检测）
    parser.add_argument("--gauge-weights", default="IQIDDET/models/guagerotation.pt",
                        help="OBB 像质计检测权重")
    parser.add_argument("--gauge-conf", type=float, default=0.25, help="OBB 置信度阈值")
    parser.add_argument("--gauge-iou", type=float, default=0.45, help="OBB IoU 阈值")
    parser.add_argument("--gauge-imgsz", type=int, default=640, help="OBB 推理图像尺寸")
    parser.add_argument("--gauge-device", default=None, help="OBB 推理设备（如 cuda:0/cpu）")
    parser.add_argument("--gauge-select", choices=["conf", "area"], default="conf",
                        help="多个检测结果时选取策略")
    # FClip（像质丝计数）
    parser.add_argument("--fclip-ckpt", default="IQIDDET/models/fclip67.pth.tar",
                        help="FClip 检查点路径")
    parser.add_argument("--fclip-config", default="IQIDDET/models/fclip_config.yaml",
                        help="FClip 模型配置 YAML")
    parser.add_argument("--fclip-device", default=None, help="FClip 推理设备")
    # OCR（文字识别，用于像质计标识读取）
    parser.add_argument("--ocr-device", choices=["cpu", "gpu"], default="gpu",
                        help="PaddleOCR 设备")
    parser.add_argument("--ocr-det-model-name", default="PP-OCRv5_server_det",
                        help="PaddleOCR 文字检测模型名称")
    parser.add_argument("--ocr-det-model-dir", default=None,
                        help="本地 PaddleOCR 文字检测模型目录")
    parser.add_argument("--ocr-det-limit-side-len", type=int, default=960,
                        help="OCR 检测输入最长边限制")
    parser.add_argument("--ocr-det-limit-type", default="max", choices=["max", "min"],
                        help="PaddleOCR 检测边长限制类型")
    parser.add_argument("--ocr-rec-model-name", default="en_PP-OCRv5_mobile_rec",
                        help="PaddleOCR 文字识别模型名称")
    parser.add_argument("--ocr-rec-model-dir", default=None,
                        help="本地 PaddleOCR 文字识别模型目录（如 IQIDDET/models/OCR_rec_inference_best_accuracy）")
    parser.add_argument("--enable-ocr-orientation", action="store_true",
                        help="启用文本裁剪方向矫正")
    parser.add_argument("--ocr-orientation-model",
                        default="IQIDDET/models/ocr_orientation_model.pth",
                        help="文本方向矫正模型权重(.pth)")
    parser.add_argument("--ocr-orientation-device", default="cuda:0",
                        help="文本方向矫正推理设备")
    parser.add_argument("--ocr-number-range", default="6,10-15",
                        help="允许的像质计标号范围，如 6,10-15")

    return parser.parse_args()


def collect_images(image_dir: Optional[Path], file_list_path: Optional[Path], max_images: Optional[int]) -> List[Path]:
    image_paths = []
    
    # Priority 1: File list
    if file_list_path:
        if not file_list_path.exists():
            raise FileNotFoundError(f"未找到文件列表: {file_list_path}")
        with open(file_list_path, 'r', encoding='utf-8') as f:
            for line in f:
                path_str = line.strip()
                if not path_str:
                    continue
                path = Path(path_str)
                if path.suffix.lower() in SUPPORTED_IMAGE_EXTS and path.is_file():
                    image_paths.append(path)
        if not image_paths:
            raise FileNotFoundError(f"文件列表 {file_list_path} 中未包含有效的图像文件")
            
    # Priority 2: Image directory
    elif image_dir:
        if not image_dir.exists():
            raise FileNotFoundError(f"输入目录不存在: {image_dir}")
        image_paths = sorted([
            p for p in image_dir.rglob('*')
            if p.suffix.lower() in SUPPORTED_IMAGE_EXTS and p.is_file()
        ])
        if not image_paths:
            raise FileNotFoundError(f"未在 {image_dir} 中找到支持的图像文件")
    else:
        raise ValueError("必须提供 --image-dir 或 --file-list 其中之一")

    if max_images is not None:
        image_paths = image_paths[:max_images]
        
    return image_paths


def _get_rel_path(image_path: Path, image_root: Optional[Path]) -> Path:
    if image_root is None:
        return Path(image_path.name)
    try:
        return image_path.relative_to(image_root)
    except ValueError:
        return Path(image_path.name)


def _build_iqi_sample_dir(vis_dir: Path, image_path: Path, image_root: Optional[Path], result_name: str) -> Path:
    rel_path = _get_rel_path(image_path, image_root)
    safe_name = str(result_name or "unknown")
    return vis_dir / safe_name / rel_path.with_suffix("")


def build_roi_detector(args: argparse.Namespace) -> Optional[WeldROIDetector]:
    if not args.roi_weights:
        return None
    print(f"加载ROI模型: {args.roi_weights}")
    return WeldROIDetector(
        model_path=args.roi_weights,
        roi_conf_threshold=args.roi_conf,
        roi_iou_threshold=args.roi_iou,
        padding_ratio=args.roi_padding
    )


def _resolve_primary_weights(args: argparse.Namespace) -> str:
    if args.primary_weights:
        return args.primary_weights
    raise ValueError("seg/det 模式需要提供 --primary-weights")


def _resolve_fusion_iou(args: argparse.Namespace) -> float:
    return args.fusion_iou


class InferencePipelineRunner:
    def __init__(self,
                 args: argparse.Namespace,
                 roi_detector: WeldROIDetector,
                 font_renderer: FontRenderer,
                 debug_root: Optional[Path],
                 corrector: Optional[WeldOrientationCorrector] = None,
                 locator: Optional[WeldSeamLocator] = None,
                 detector: Optional[WeldDefectPositionDetector] = None,
                 iqi_inferencer=None):
        self.args = args
        self.mode = args.mode
        self.roi_detector = roi_detector
        self.font_renderer = font_renderer
        self.debug_root = debug_root
        self.output_dir = Path(args.output_dir) if args.output_dir else None
        self.corrector = corrector
        self.locator = locator
        self.detector = detector
        self.iqi_inferencer = iqi_inferencer
        self.iqi_image_root = Path(args.image_dir).resolve() if args.image_dir else None
        self.iqi_vis_dir = (
            self.output_dir / "iqi_vis"
            if self.output_dir is not None and self.iqi_inferencer is not None
            else None
        )

        self.det_model_cls = rfdet_pipeline.RFDetrDetectionModel
        self.seg_model_cls = rfdet_pipeline.RFDetrSegmentationModel
        self.detection_config_cls = rfdet_pipeline.RFDetrDetectionConfig
        self.run_detection_func = rfdet_pipeline.run_rfdet_detection
        self.process_segmentation_func = rfdet_pipeline.process_roi_and_segmentation

        self.primary_weights = _resolve_primary_weights(args)
        self.primary_confidence = args.primary_conf
        self.fusion_iou = _resolve_fusion_iou(args)
        self.enable_wide_slice = bool(getattr(args, "wide_slice", False))

        self.primary_model = self._build_primary_model()

    def run(self, image_inputs: List[PreparedImageInput]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        total = len(image_inputs)

        for idx, image_input in enumerate(tqdm(image_inputs, desc="推理中")):
            image_path = image_input.original_path
            processing_path = image_input.processing_path
            if self.output_dir:
                self._update_progress_file(self.output_dir, idx, total, image_path.name, stage="running")
            try:
                # 输入预处理：16bit / DICOM 先转换为 8bit，再进入后续既有流程
                rois, weld_location, defect_position, width, height, correction_info, corrected_img = \
                    self._process_image(processing_path)
                label = correction_info.get('label', 0)
                transform = LABEL_TO_FRONTEND_TRANSFORM.get(label, {"rotation": 0, "flip": False})

                # IQI Grade Inference 也使用预处理后的 8bit 图像，避免 DICOM / 16bit 分支差异
                iqi_result: Optional[Dict[str, Any]] = None
                if self.iqi_inferencer is not None:
                    try:
                        want_iqi_vis = self.iqi_vis_dir is not None
                        iqi_record, artifacts = self.iqi_inferencer.infer_image_path(
                            processing_path,
                            return_debug_artifacts=want_iqi_vis,
                        )
                        iqi_record["image_path"] = str(image_path)
                        if want_iqi_vis and artifacts is not None and artifacts.get("image") is not None:
                            try:
                                sample_dir = _build_iqi_sample_dir(
                                    self.iqi_vis_dir,
                                    image_path,
                                    self.iqi_image_root,
                                    str(iqi_record.get("result_name", "unknown")),
                                )
                                iqi_record.update(
                                    save_debug_visualizations(
                                        output_dir=self.output_dir,
                                        sample_dir=sample_dir,
                                        image=artifacts["image"],
                                        full_ocr_result=iqi_record.get("full_image_ocr") or iqi_record.get("ocr") or {},
                                        full_ocr_image=artifacts.get("full_ocr_input"),
                                        roi_info=iqi_record.get("roi") or {},
                                        roi_image=artifacts.get("roi_image"),
                                        roi_gray=artifacts.get("roi_gray"),
                                        roi_ocr_result=iqi_record.get("roi_ocr") or {},
                                        wire_result=iqi_record.get("wire") or {},
                                        visualization=iqi_record.get("visualization") or {},
                                        plate_code=iqi_record.get("plate_code"),
                                        grade=iqi_record.get("grade"),
                                        wire_count=iqi_record.get("wire_count"),
                                    )
                                )
                            except Exception as iqi_vis_exc:
                                print(f"[警告] IQI 调试图保存失败 ({image_path.name}): {iqi_vis_exc}")
                        iqi_result = iqi_record
                    except Exception as iqi_exc:
                        print(f"[警告] IQI 推理失败 ({image_path.name}): {iqi_exc}")

                # Compute grayscale density (film blackness) from the original source image.
                # Detection still runs on the preprocessed 8-bit branch, but density sampling
                # should use native high-bit data after applying the same correction label so
                # coordinates remain aligned with weld_location keypoints.
                grayscale_density: Optional[str] = None
                density_image = None
                try:
                    density_image = _load_density_image(image_path, label)
                except Exception as density_exc:
                    print(f"[警告] 原始灰度图加载失败，回退使用推理图 ({image_path.name}): {density_exc}")
                    density_image = corrected_img

                if density_image is not None:
                    try:
                        if weld_location:
                            # B path detected: use ellipse/vertical clock positions
                            grayscale_density = compute_grayscale_loc0(density_image, weld_location)
                        if grayscale_density is None:
                            # Fallback to linear sampling (D path or no location detection)
                            grayscale_density = compute_grayscale_loc1(density_image)
                    except Exception as gs_exc:
                        print(f"[警告] 灰度值计算失败 ({image_path.name}): {gs_exc}")

                results.append({
                    "mode": self.mode,
                    "image_path": str(image_path),
                    "width": width,
                    "height": height,
                    "num_rois": len(rois),
                    "preprocessed_path": str(processing_path) if image_input.converted_to_8bit else "",
                    "correction": {
                        "label": label,
                        "rotation": transform["rotation"],
                        "flip": transform["flip"],
                    },
                    "rois": rois,
                    "weld_location": weld_location,
                    "defect_position": defect_position,
                    "ocr": iqi_result,
                    "grayscale_density": grayscale_density,
                })
            except Exception as exc:
                print(f"[警告] 处理 {image_path} 时出错: {exc}")

            # Update progress after both detection and OCR are done for this image
            if self.output_dir:
                self._update_progress_file(self.output_dir, idx + 1, total, image_path.name, stage="running")

        return results

    def _update_progress_file(self, output_dir: Path, current: int, total: int, last_file: str, stage: str = "running"):
        progress_file = output_dir / "progress.json"
        try:
            with open(progress_file, "w") as f:
                json.dump({
                    "current": current,
                    "total": total,
                    "last_file": last_file,
                    "stage": stage,
                }, f)
        except Exception:
            pass  # Ignore write errors to avoid crashing inference

    def _build_primary_model(self):
        if self.mode == "det":
            return self.det_model_cls(
                model_path=self.primary_weights,
                confidence=self.primary_confidence,
                device=self.args.det_device,
                model_variant="large"
            )
        return self.seg_model_cls(
            model_path=self.primary_weights,
            confidence=self.primary_confidence,
            device=self.args.device
        )

    def _image_debug_dir(self, image_path: Path) -> Optional[Path]:
        if self.debug_root is None:
            return None
        return self.debug_root / image_path.stem

    def _process_image(self, image_path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]], int, int, dict, Any]:
        image = load_image(image_path)
        
        # 默认矫正信息（未进行矫正时使用）
        correction_info: dict = {'label': 0, 'corrected': False}

        # A: Apply weld orientation correction preprocessing if enabled
        if self.corrector is not None:
            image, correction_info = self.corrector.correct_image(
                image, 
                verbose=self.args.correction_verbose
            )
            
            # Save corrected image if a directory is specified
            save_dir = getattr(self.args, 'save_corrected_dir', None)
            if save_dir:
                save_dir_path = Path(save_dir)
                save_dir_path.mkdir(parents=True, exist_ok=True)
                corrected_path = save_dir_path / image_path.name
                import cv2
                # Use imencode and tofile to support potential Chinese paths
                ext = image_path.suffix if image_path.suffix else '.jpg'
                cv2.imencode(ext, image)[1].tofile(str(corrected_path))
            # Optionally save corrected image for debugging
            elif self.debug_root and correction_info.get('corrected', False):
                corrected_dir = self.debug_root / "corrected_images"
                corrected_dir.mkdir(parents=True, exist_ok=True)
                corrected_path = corrected_dir / f"corrected_{image_path.name}"
                import cv2
                ext = image_path.suffix if image_path.suffix else '.jpg'
                cv2.imencode(ext, image)[1].tofile(str(corrected_path))
        
        h, w = image.shape[:2]
        debug_dir = self._image_debug_dir(image_path)

        # B: 焊缝位置检测（基于负片+窗口化预处理图，与C路径并行，互不影响）
        weld_location: List[Dict[str, Any]] = []
        if self.locator is not None:
            try:
                weld_location = self.locator.predict(image)
                if getattr(self.args, 'location_verbose', False) and weld_location:
                    print(f"  [位置检测] {image_path.name}: 检测到 {len(weld_location)} 个目标")
                # 保存带关键点可视化的图像
                save_loc_dir = getattr(self.args, 'save_location_dir', None)
                if save_loc_dir and weld_location:
                    import cv2
                    vis = image.copy()
                    for det in weld_location:
                        x1, y1, x2, y2 = det['bbox']
                        label = f"{det['class']} {det['confidence']:.2f}"
                        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(vis, label, (x1, max(y1 - 6, 0)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        for kp in det['keypoints']:
                            cx, cy = int(kp['x']), int(kp['y'])
                            cv2.circle(vis, (cx, cy), 4, (0, 0, 255), -1)
                            cv2.putText(vis, str(kp['id']), (cx + 5, cy - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1)
                    save_loc_path = Path(save_loc_dir)
                    save_loc_path.mkdir(parents=True, exist_ok=True)
                    ext = image_path.suffix if image_path.suffix else '.jpg'
                    out_name = save_loc_path / f"loc_{image_path.stem}{ext}"
                    cv2.imencode(ext, vis)[1].tofile(str(out_name))
            except Exception as loc_exc:
                print(f"[警告] 焊缝位置检测失败 ({image_path.name}): {loc_exc}")

        # D: 缺陷位置检测2（YOLO detection + OCR，与B/C路径并行，互不影响）
        defect_position: Optional[Dict[str, Any]] = None
        if self.detector is not None:
            try:
                defect_position = self.detector.predict(image)
                if getattr(self.args, 'location2_verbose', False) and defect_position:
                    detected = defect_position.get('detected', False)
                    origin_x = defect_position.get('origin_x')
                    origin_y = defect_position.get('origin_y')
                    print(f"  [缺陷位置检测2] {image_path.name}: "
                          f"{'检测到原点 ({:.1f}, {:.1f})'.format(origin_x, origin_y) if detected else '未检测到原点'}")
                # 保存带标注的可视化图像
                save_loc2_dir = getattr(self.args, 'save_location2_dir', None)
                if save_loc2_dir and defect_position and defect_position.get('detected'):
                    import cv2
                    vis2 = image.copy()
                    for det in defect_position.get('detections', []):
                        x1, y1, x2, y2 = det['bbox']
                        color = (0, 255, 0) if det['class_id'] == 0 else (255, 100, 0)
                        cv2.rectangle(vis2, (x1, y1), (x2, y2), color, 2)
                        label2 = f"{det['class_name']} {det['confidence']:.2f}"
                        cv2.putText(vis2, label2, (x1, max(y1 - 6, 0)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    ox = int(defect_position['origin_x'])
                    oy = int(defect_position['origin_y'])
                    cv2.drawMarker(vis2, (ox, oy), (0, 0, 255), cv2.MARKER_CROSS, 50, 3)
                    cv2.circle(vis2, (ox, oy), 30, (0, 255, 0), 2)
                    save_loc2_path = Path(save_loc2_dir)
                    save_loc2_path.mkdir(parents=True, exist_ok=True)
                    ext = image_path.suffix if image_path.suffix else '.jpg'
                    out_name2 = save_loc2_path / f"loc2_{image_path.stem}{ext}"
                    cv2.imencode(ext, vis2)[1].tofile(str(out_name2))
            except Exception as det_exc:
                print(f"[警告] 缺陷位置检测2失败 ({image_path.name}): {det_exc}")

        # C: 缺陷类型检测（使用矫正后原始图）
        wide_slice_cfg = rfdet_pipeline.WideSliceConfig(enabled=True) if self.enable_wide_slice else None
        if self.mode == "det":
            config = self.detection_config_cls(
                roi_detector=self.roi_detector,
                detection_model=self.primary_model,
                enhance_mode=self.args.enhance_mode,
                fusion_iou=self.fusion_iou,
                font_renderer=self.font_renderer,
                debug_root=debug_dir,
                wide_slice=wide_slice_cfg
            )
            rois = self.run_detection_func(image, config)
        else:
            if self.roi_detector is None:
                raise ValueError("seg 模式必须提供 ROI 检测器")
            rois = self.process_segmentation_func(
                image=image,
                roi_detector=self.roi_detector,
                seg_model=self.primary_model,
                enhance_mode=self.args.enhance_mode,
                font_renderer=self.font_renderer,
                debug_dir=debug_dir,
                wide_slice=wide_slice_cfg,
                fusion_iou=self.fusion_iou
            )
        if debug_dir is not None:
            final_detections: List[Dict[str, Any]] = []
            if self.mode == "det":
                for roi in rois:
                    final_detections.extend(roi.get("detections", []))
            else:
                for roi in rois:
                    final_detections.extend(roi.get("defects", []))
            rfdet_pipeline._save_debug_image(
                image,
                final_detections,
                debug_dir / "final_result.jpg",
                self.font_renderer
            )

        return rois, weld_location, defect_position, w, h, correction_info, image


def main():
    # Fix for PaddlePaddle dynamic library loading (cuDNN, cuBLAS)
    try:
        import os
        os.makedirs("/usr/local/cuda/lib64", exist_ok=True)
        cudnn_src = "/usr/lib/x86_64-linux-gnu/libcudnn.so.8"
        cublas_src = "/usr/local/lib/python3.10/dist-packages/nvidia/cublas/lib/libcublas.so.12"
        cudnn_dst = "/usr/local/cuda/lib64/libcudnn.so"
        cublas_dst = "/usr/local/cuda/lib64/libcublas.so"
        
        if os.path.exists(cudnn_src) and not os.path.exists(cudnn_dst):
            os.symlink(cudnn_src, cudnn_dst)
        if os.path.exists(cublas_src) and not os.path.exists(cublas_dst):
            os.symlink(cublas_src, cublas_dst)
    except Exception:
        pass

    args = parse_args()
    
    image_dir = Path(args.image_dir) if args.image_dir else None
    file_list = Path(args.file_list) if args.file_list else None
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_paths = collect_images(image_dir, file_list, args.max_images)
    roi_detector = build_roi_detector(args)

    if args.mode in {"seg", "det"} and roi_detector is None:
        raise ValueError(f"{args.mode} 模式必须提供 --roi-weights 以执行ROI检测")

    font_renderer = FontRenderer(font_path=args.font_path, font_size=args.font_size)

    debug_root = (output_dir / "temp") if DEBUG_STEP else None
    if debug_root is not None:
        debug_root.mkdir(parents=True, exist_ok=True)
    
    # Initialize weld orientation corrector if enabled
    corrector = None
    if args.enable_correction:
        print(f"启用焊缝底片方向矫正,模型路径: {args.correction_model}")
        corrector = WeldOrientationCorrector(
            model_path=args.correction_model,
            model_type='resnet50'
        )

    # Initialize weld seam locator (B path) if --enable-location is set
    locator = None
    if args.enable_location:
        location_model_path = Path(args.location_model)
        print(f"启用焊缝位置检测，模型路径: {location_model_path}")
        if not location_model_path.exists():
            raise FileNotFoundError(
                f"焊缝位置检测模型未找到: {location_model_path}\n"
                "请确认路径正确，或通过 --location-model 指定正确路径"
            )
        try:
            locator = WeldSeamLocator(
                model_path=str(location_model_path),
                conf_threshold=args.location_conf,
            )
        except Exception as e:
            print(f"[警告] 焊缝位置检测器初始化失败: {e}")
    else:
        print("[信息] 未启用焊缝位置检测（使用 --enable-location 开启）")

    # Initialize weld defect position detector (D path) if --enable-location2 is set
    detector = None
    if args.enable_location2:
        location2_model_path = Path(args.location2_model)
        print(f"启用缺陷位置检测2，模型路径: {location2_model_path}")
        if not location2_model_path.exists():
            raise FileNotFoundError(
                f"缺陷位置检测2模型未找到: {location2_model_path}\n"
                "请确认路径正确，或通过 --location2-model 指定正确路径"
            )
        try:
            def _abs(p):
                from pathlib import Path
                return str(Path(p).resolve()) if p else p

            detector = WeldDefectPositionDetector(
                model_path=str(location2_model_path),
                conf_threshold=args.location2_conf
            )
        except Exception as e:
            print(f"[警告] 缺陷位置检测2初始化失败: {e}")
    else:
        print("[信息] 未启用缺陷位置检测2（使用 --enable-location2 开启）")

    # Initialize IQI Grade Inferencer if --enable-iqi is set
    iqi_inferencer = None
    if args.enable_iqi:
        if _IQI_AVAILABLE:
            print("启用 IQI 像质计识别（IQIDDET 集成，与缺陷检测独立并行）")
            print(f"IQI 像质计识,模型配置路径:gauge-weights:{args.gauge_weights}")
            print(f"FClip 检查点路径:fclip-ckpt:{args.fclip_ckpt}")
            print(f"FClip 模型配置路径:fclip-config:{args.fclip_config}")
            print(f"OCR 检测模型目录:ocr-det-model-dir:{args.ocr_det_model_dir}")
            print(f"OCR 识别模型目录:ocr-rec-model-dir:{args.ocr_rec_model_dir}")


            try:
                # 将所有路径参数转为绝对路径，避免子进程(ocr_paddle_worker)工作目录
                # 与主进程不同导致相对路径失效
                def _abs(p):
                    return str(Path(p).resolve()) if p else p

                # 当提供本地 rec_model_dir 时，不传 rec_model_name，
                # 让 PaddleOCR 直接从目录内 inference.yml 读取 model_name，
                # 避免默认 model_name 与本地模型不匹配导致 AssertionError。
                iqi_inferencer = IQIInferencer(
                    gauge_weights=_abs(args.gauge_weights),
                    fclip_ckpt=_abs(args.fclip_ckpt),
                    gauge_conf=args.gauge_conf,
                    gauge_iou=args.gauge_iou,
                    gauge_imgsz=args.gauge_imgsz,
                    gauge_device=args.gauge_device,
                    gauge_select=args.gauge_select,
                    ocr_device=args.ocr_device,
                    ocr_det_model_name=args.ocr_det_model_name,
                    ocr_det_model_dir=_abs(args.ocr_det_model_dir),
                    ocr_rec_model_name=None if args.ocr_rec_model_dir else args.ocr_rec_model_name,
                    ocr_rec_model_dir=_abs(args.ocr_rec_model_dir),
                    ocr_det_limit_side_len=args.ocr_det_limit_side_len,
                    ocr_det_limit_type=args.ocr_det_limit_type,
                    enable_ocr_orientation=args.enable_ocr_orientation,
                    ocr_orientation_model=_abs(args.ocr_orientation_model),
                    ocr_orientation_device=args.ocr_orientation_device,
                    ocr_number_range=args.ocr_number_range,
                    fclip_device=args.fclip_device,
                    fclip_model_config=_abs(args.fclip_config),
                )
            except Exception as iqi_init_err:
                print(f"[警告] IQIInferencer 初始化失败，跳过 IQI 推理: {iqi_init_err}")
        else:
            print("[警告] --enable-iqi 已指定，但 IQIInferencer 未加载，跳过 IQI 推理")

    runner = InferencePipelineRunner(
        args=args,
        roi_detector=roi_detector,
        font_renderer=font_renderer,
        debug_root=debug_root,
        corrector=corrector,
        locator=locator,
        detector=detector,
        iqi_inferencer=iqi_inferencer,
    )
    prepared_root = output_dir / "prepared_inputs"
    image_inputs = [_prepare_image_input(path, prepared_root) for path in image_paths]

    results = runner.run(image_inputs)

    # Save weld detection results
    results_path = Path(args.results_json)
    if not results_path.is_absolute():
        results_path = output_dir / results_path

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({"mode": args.mode, "results": results}, f, indent=2, ensure_ascii=False)

    print(f"\n推理完成: 模式={args.mode}，共处理 {len(results)} 张图像。")
    print(f"结果JSON: {results_path}")

    # Save IQI results summary JSON（只要 --enable-iqi 就保存，不依赖初始化是否成功）
    if args.enable_iqi:
        if iqi_inferencer is not None:
            iqi_inferencer.close()
        if not _IQI_AVAILABLE:
            # IQI 模块加载失败（如缺少依赖），写入错误占位文件后继续
            iqi_out_path = output_dir / args.iqi_results_json
            with open(iqi_out_path, "w", encoding="utf-8") as f:
                json.dump({"ok": False, "fatal_error": str(_iqi_err),
                           "results": []}, f, indent=2, ensure_ascii=False)
            print(f"[警告] IQI 模块不可用，已写入错误占位: {iqi_out_path}")
        else:
            iqi_raw_records = [r.get("ocr") for r in results if r.get("ocr") is not None]
            delivery_records = [build_delivery_record(rec) for rec in iqi_raw_records]
            summary = build_iqi_statistics(iqi_raw_records)
            image_root = Path(args.image_dir).resolve() if args.image_dir else None
            iqi_payload = {
                "schema": "iqi_grade_batch_v1",
                "ok": True,
                "fatal_error": None,
                "meta": {
                    "created_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                    "image_root": str(image_root) if image_root is not None else None,
                    **(iqi_inferencer.get_runtime_meta() if iqi_inferencer is not None else {}),
                    "ocr_device": args.ocr_device,
                    "ocr_det_model_name": args.ocr_det_model_name,
                    "ocr_det_model_dir": args.ocr_det_model_dir,
                    "ocr_rec_model_name": args.ocr_rec_model_name,
                    "ocr_rec_model_dir": args.ocr_rec_model_dir,
                    "ocr_det_limit_side_len": args.ocr_det_limit_side_len,
                    "ocr_det_limit_type": args.ocr_det_limit_type,
                    "ocr_number_range": args.ocr_number_range,
                    "enable_ocr_orientation": args.enable_ocr_orientation,
                    "ocr_orientation_model": args.ocr_orientation_model,
                    "ocr_orientation_device": args.ocr_orientation_device,
                    "vis_dir": "iqi_vis" if iqi_inferencer is not None else None,
                },
                "summary": {
                    "images_total": summary["images_total"],
                    "success_total": summary["success_total"],
                    "failure_total": summary["failure_total"],
                    "result_code_hist": summary["result_code_hist"],
                    "result_code_hist_named": summary["result_code_hist_named"],
                    "iqi_type_hist": summary["iqi_type_hist"],
                    "grade_hist": summary["grade_hist"],
                    "field_totals": summary["field_totals"],
                    "images_with_general_fields": summary["images_with_general_fields"],
                    "images_with_iqi_marker": summary["images_with_iqi_marker"],
                },
                "results": delivery_records,
            }
            iqi_out_path = output_dir / args.iqi_results_json
            with open(iqi_out_path, "w", encoding="utf-8") as f:
                json.dump(iqi_payload, f, indent=2, ensure_ascii=False)
            print(f"IQI 推理完成: 共处理 {len(delivery_records)} 张图像，结果JSON: {iqi_out_path}")


if __name__ == "__main__":
    main()
