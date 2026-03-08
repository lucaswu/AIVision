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
import json
import sys
import os
import ssl

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
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

DEBUG_STEP = True

from convert.pj.yolo_roi_extractor import WeldROIDetector  # noqa: E402
from utils.pipeline_utils import FontRenderer, load_image  # noqa: E402
from utils import detection_pipeline as rfdet_pipeline  # noqa: E402
from utils.weld_correction import WeldOrientationCorrector  # noqa: E402
from utils.weld_locaiont_0 import WeldSeamLocator, DEFAULT_LOCATION_MODEL_PATH  # noqa: E402
from utils.weld_locaiont_1 import WeldDefectPositionDetector, DEFAULT_LOCATION1_MODEL_PATH  # noqa: E402
from utils.weld_OCR import OCRRunner, _OCR_UTILS_AVAILABLE  # noqa: E402


SUPPORTED_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')

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
    parser.add_argument("--primary-conf", type=float, default=0.25, help="主模型置信度阈值")
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

    # OCR集成参数
    parser.add_argument("--enable-ocr", action="store_true",
                        help="启用OCR识别（与缺陷检测并行，输入为矫正后的原始图C）")
    parser.add_argument("--ocr-max-size", type=int, default=1920,
                        help="OCR处理时的最大图像边长（默认1920）")
    parser.add_argument("--no-ocr-annotation", action="store_true",
                        help="不保存OCR标注图片")
    parser.add_argument("--ocr-results-json", default="ocr_results.json",
                        help="OCR结果JSON文件名（相对output_dir，默认ocr_results.json）")

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
                 ocr_runner: Optional[OCRRunner] = None):
        self.args = args
        self.mode = args.mode
        self.roi_detector = roi_detector
        self.font_renderer = font_renderer
        self.debug_root = debug_root
        self.output_dir = Path(args.output_dir) if args.output_dir else None
        self.corrector = corrector
        self.locator = locator
        self.detector = detector
        self.ocr_runner = ocr_runner

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

    def run(self, image_paths: List[Path]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        total = len(image_paths)

        # Pre-create OCR annotated-images directory once (avoids repeated mkdir calls)
        ocr_annotated_dir: Optional[Path] = None
        if self.ocr_runner is not None and self.ocr_runner.save_annotations and self.output_dir:
            ocr_annotated_dir = self.output_dir / "annotated_images"
            ocr_annotated_dir.mkdir(parents=True, exist_ok=True)

        for idx, image_path in enumerate(tqdm(image_paths, desc="推理中")):
            try:
                # A→B/D: weld seam / defect-position detection; A→correction→C: defect type detection
                rois, weld_location, defect_position, width, height, correction_info, corrected_img = \
                    self._process_image(image_path)
                label = correction_info.get('label', 0)
                transform = LABEL_TO_FRONTEND_TRANSFORM.get(label, {"rotation": 0, "flip": False})

                # OCR on corrected image C (independent of defect detection)
                ocr_result: Optional[Dict[str, Any]] = None
                if self.ocr_runner is not None and corrected_img is not None:
                    try:
                        ocr_save_path: Optional[str] = None
                        if ocr_annotated_dir is not None:
                            ocr_save_path = str(ocr_annotated_dir / f"{image_path.stem}_annotated.jpg")
                        ocr_result = self.ocr_runner.process_image_array(
                            corrected_img, image_path.name, ocr_save_path
                        )
                        if ocr_result:
                            self.ocr_runner.results.append(ocr_result)
                            self.ocr_runner.statistics.append(
                                self.ocr_runner._extract_statistics(ocr_result)
                            )
                    except Exception as ocr_exc:
                        print(f"[警告] OCR失败 ({image_path.name}): {ocr_exc}")

                results.append({
                    "mode": self.mode,
                    "image_path": str(image_path),
                    "width": width,
                    "height": height,
                    "num_rois": len(rois),
                    "correction": {
                        "label": label,
                        "rotation": transform["rotation"],
                        "flip": transform["flip"],
                    },
                    "rois": rois,
                    "weld_location": weld_location,
                    "defect_position": defect_position,
                    "ocr": ocr_result,
                })
            except Exception as exc:
                print(f"[警告] 处理 {image_path} 时出错: {exc}")

            # Update progress after both detection and OCR are done for this image
            if self.output_dir:
                self._update_progress_file(self.output_dir, idx + 1, total, image_path.name)

        return results

    def _update_progress_file(self, output_dir: Path, current: int, total: int, last_file: str):
        progress_file = output_dir / "progress.json"
        try:
            with open(progress_file, "w") as f:
                json.dump({
                    "current": current,
                    "total": total,
                    "last_file": last_file
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
                        label2 = det['class_name']
                        if det.get('text'):
                            label2 += f" '{det['text']}'"
                        label2 += f" {det['confidence']:.2f}"
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
            detector = WeldDefectPositionDetector(
                model_path=str(location2_model_path),
                conf_threshold=args.location2_conf,
            )
        except Exception as e:
            print(f"[警告] 缺陷位置检测2初始化失败: {e}")
    else:
        print("[信息] 未启用缺陷位置检测2（使用 --enable-location2 开启）")

    # Initialize OCR runner if --enable-ocr is set
    ocr_runner = None
    if args.enable_ocr:
        if _OCR_UTILS_AVAILABLE:
            print("启用OCR识别（在矫正后图像C上运行，与缺陷检测独立并行）")
            ocr_runner = OCRRunner(
                max_image_size=args.ocr_max_size,
                save_annotations=not args.no_ocr_annotation,
                verbose=False,
            )
        else:
            print("[警告] --enable-ocr 已指定，但OCR工具未加载，跳过OCR")

    runner = InferencePipelineRunner(
        args=args,
        roi_detector=roi_detector,
        font_renderer=font_renderer,
        debug_root=debug_root,
        corrector=corrector,
        locator=locator,
        detector=detector,
        ocr_runner=ocr_runner,
    )
    results = runner.run(image_paths)

    # Save weld detection results
    results_path = Path(args.results_json)
    if not results_path.is_absolute():
        results_path = output_dir / results_path

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({"mode": args.mode, "results": results}, f, indent=2, ensure_ascii=False)

    print(f"\n推理完成: 模式={args.mode}，共处理 {len(results)} 张图像。")
    print(f"结果JSON: {results_path}")

    # Save OCR outputs (mirrors OCR_main.py output files)
    if ocr_runner is not None:
        ocr_runner.save_statistics(output_dir)
        ocr_runner.save_detailed_results(output_dir)
        ocr_runner.save_results_json(output_dir, filename=args.ocr_results_json)
        print(f"OCR完成: 共处理 {len(ocr_runner.results)} 张图像。")


if __name__ == "__main__":
    main()
