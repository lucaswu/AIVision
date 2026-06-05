#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIVision 推理服务 API 入口
提供 HTTP 接口调用焊缝检测模型

启动方式：
    uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import argparse
import importlib.util
import json
import io
import os
import subprocess
import sys
import time
import asyncio
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks, File as FastAPIFile, Form, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 确保能导入模型代码
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 延迟导入 torch 以获取 GPU 状态
_torch_available = False
_cuda_available = False

try:
    import torch
    _torch_available = True
    _cuda_available = torch.cuda.is_available()
except ImportError:
    pass

# ==============================================================================
# FastAPI 应用配置
# ==============================================================================

app = FastAPI(
    title="AIVision Inference Service",
    description="焊缝缺陷检测 AI 推理服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局状态存储
inference_tasks: Dict[str, Dict[str, Any]] = {}
executor = ThreadPoolExecutor(max_workers=2)
THUMBNAIL_DICOM_EXTENSIONS = {".dcm", ".dicom", ".dic", ".diconde"}
THUMBNAIL_TIFF_EXTENSIONS = {".tif", ".tiff"}
INFERENCE_EXECUTION_MODE = os.environ.get("INFERENCE_EXECUTION_MODE", "direct").strip().lower()
INFERENCE_PREWARM_ENABLED = os.environ.get("INFERENCE_PREWARM_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
INFERENCE_HEALTH_REQUIRES_WARMUP = os.environ.get(
    "INFERENCE_HEALTH_REQUIRES_WARMUP", "true"
).strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_runtime_cache_lock = threading.Lock()
_runtime_execution_lock = threading.Lock()
_weld_pipeline_lock = threading.Lock()
_runtime_cache: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
_weld_pipeline_module = None
_runtime_warmup_completed = False
_runtime_warmup_error: Optional[str] = None


class _PrefixedStream:
    """Prefix redirected stdout/stderr lines so task logs stay readable."""

    def __init__(self, prefix: str, stream):
        self.prefix = prefix
        self.stream = stream
        self._buffer = ""

    def write(self, data: str) -> int:
        text = str(data)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line:
                self.stream.write(f"{self.prefix}{line}\n")
            else:
                self.stream.write("\n")
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            self.stream.write(f"{self.prefix}{self._buffer}")
            self._buffer = ""
        self.stream.flush()


def _load_weld_pipeline_module():
    """Load /app/model/run_inference_pipeline.py without colliding with IQIDDET's file of the same name."""
    global _weld_pipeline_module
    if _weld_pipeline_module is not None:
        return _weld_pipeline_module

    with _weld_pipeline_lock:
        if _weld_pipeline_module is not None:
            return _weld_pipeline_module

        module_name = "aivision_weld_run_inference_pipeline"
        existing = sys.modules.get(module_name)
        if existing is not None:
            _weld_pipeline_module = existing
            return existing

        module_path = PROJECT_ROOT / "run_inference_pipeline.py"
        if not module_path.exists():
            raise FileNotFoundError(f"未找到焊缝推理流水线脚本: {module_path}")

        project_root_str = str(PROJECT_ROOT)
        while project_root_str in sys.path:
            sys.path.remove(project_root_str)
        sys.path.insert(0, project_root_str)

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载焊缝推理流水线脚本: {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        _weld_pipeline_module = module
        return module


def _normalize_thumbnail_image(image: np.ndarray, invert: bool = False) -> np.ndarray:
    if image is None:
        raise ValueError("空图像无法生成缩略图")

    if image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    if image.dtype == np.uint8 and not invert:
        return image

    arr = image.astype(np.float32, copy=False)
    low = float(np.min(arr))
    high = float(np.max(arr))

    if high <= low:
        out = np.zeros(arr.shape, dtype=np.uint8)
    else:
        arr = np.clip(arr, low, high)
        arr = (arr - low) / (high - low) * 255.0
        if invert:
            arr = 255.0 - arr
        out = arr.astype(np.uint8)

    if out.ndim == 3 and out.shape[2] == 4:
        out = cv2.cvtColor(out, cv2.COLOR_BGRA2BGR)
    return out


def _decode_tiff_bytes(content: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("无法解码 TIFF 图像")
    return image


def _decode_dicom_bytes(content: bytes) -> tuple[np.ndarray, bool]:
    try:
        import pydicom
    except Exception as exc:
        raise RuntimeError("pydicom 未安装，无法生成 DICOM 缩略图") from exc

    ds = pydicom.dcmread(io.BytesIO(content), force=True)
    if not hasattr(ds, "PixelData"):
        raise ValueError("DICOM 缺少 PixelData")

    image = ds.pixel_array
    samples_per_pixel = int(getattr(ds, "SamplesPerPixel", 1) or 1)

    if image.ndim == 4:
        image = image[0]
    if image.ndim == 3 and samples_per_pixel == 1:
        image = image[0]

    image = image.astype(np.float32)

    if samples_per_pixel == 1:
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        image = image * slope + intercept

    invert = str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1"
    return image, invert


def _convert_to_thumbnail_jpeg(content: bytes, filename: str, quality: int) -> bytes:
    suffix = Path(filename or "image").suffix.lower()

    if suffix in THUMBNAIL_DICOM_EXTENSIONS:
        image, invert = _decode_dicom_bytes(content)
    elif suffix in THUMBNAIL_TIFF_EXTENSIONS:
        image = _decode_tiff_bytes(content)
        invert = False
    else:
        raise ValueError(f"不支持的缩略图源格式: {suffix or 'unknown'}")

    display_image = _normalize_thumbnail_image(image, invert=invert)
    ok, encoded = cv2.imencode(".jpg", display_image, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("JPEG 编码失败")
    return encoded.tobytes()


# ==============================================================================
# 请求/响应模型
# ==============================================================================

class InferenceRequest(BaseModel):
    """推理请求"""
    task_id: str = Field(..., description="任务ID")
    file_paths: List[str] = Field(..., description="文件路径列表（相对于数据卷）")
    mode: str = Field(default="det", description="推理模式: det(检测) 或 seg(分割)")
    device: str = Field(default="cuda:0", description="推理设备: cuda:0, cuda:1, cpu")
    roi_weights: Optional[str] = Field(default=None, description="ROI模型权重路径")
    primary_weights: Optional[str] = Field(default=None, description="主模型权重路径")
    primary_conf: float = Field(default=0.15, description="主模型置信度阈值")
    wide_slice: bool = Field(default=True, description="是否启用横切纵拼推理")
    enable_location: bool = Field(default=True, description="是否启用焊缝位置检测")
    location_conf: float = Field(default=0.6, description="焊缝位置检测置信度阈值")
    enable_location2: bool = Field(default=True, description="是否启用缺陷位置检测2（location_1.pt）")
    location2_conf: float = Field(default=0.25, description="缺陷位置检测2置信度阈值")
    enable_iqi: bool = Field(default=True, description="是否启用IQI像质计识别")


def _build_runtime_args(
    request: InferenceRequest,
    output_dir: Path,
    file_list_path: Path,
) -> argparse.Namespace:
    """Build an argparse-like namespace for in-process inference execution."""
    rip = _load_weld_pipeline_module()

    roi_weights = request.roi_weights or os.environ.get(
        "ROI_WEIGHTS", "/app/model/weights/weldROI4.pt"
    )
    primary_weights = request.primary_weights or os.environ.get(
        "PRIMARY_WEIGHTS", "/app/model/weights/primary-weights.pth"
    )
    device = request.device if _cuda_available else "cpu"
    correction_model = os.environ.get(
        "CORRECTION_MODEL", "/app/model/weights/weld_orientation_model.pth"
    )
    location_model = os.environ.get(
        "LOCATION_MODEL", "/app/model/weights/location_0.pt"
    )
    location2_model = os.environ.get(
        "LOCATION2_MODEL", "/app/model/weights/location_1.pt"
    )

    args = argparse.Namespace(
        image_dir=None,
        file_list=str(file_list_path),
        output_dir=str(output_dir),
        results_json="inference_results.json",
        mode=request.mode,
        max_images=None,
        roi_weights=roi_weights,
        roi_conf=0.25,
        roi_iou=0.45,
        roi_padding=0.1,
        enhance_mode="windowing",
        font_path=None,
        font_size=20,
        primary_weights=primary_weights,
        fusion_iou=0.5,
        primary_conf=request.primary_conf,
        device=device,
        det_device=device,
        wide_slice=bool(request.wide_slice),
        enable_correction=os.path.exists(correction_model),
        correction_model=correction_model,
        correction_verbose=False,
        save_corrected_dir=None,
        enable_location=bool(request.enable_location and os.path.exists(location_model)),
        location_model=location_model,
        location_conf=request.location_conf,
        location_verbose=False,
        save_location_dir=None,
        enable_location2=bool(request.enable_location2 and os.path.exists(location2_model)),
        location2_model=location2_model,
        location2_conf=request.location2_conf,
        location2_verbose=False,
        save_location2_dir=None,
        enable_iqi=bool(request.enable_iqi),
        iqi_results_json="iqi_grade_results.json",
        gauge_weights=os.environ.get("GAUGE_WEIGHTS", "IQIDDET/models/guagerotation.pt"),
        gauge_conf=0.25,
        gauge_iou=0.45,
        gauge_imgsz=640,
        gauge_device="cuda:0" if _cuda_available else "cpu",
        gauge_select="conf",
        fclip_ckpt=os.environ.get("FCLIP_CKPT", "IQIDDET/models/fclip67.pth.tar"),
        fclip_config=os.environ.get("FCLIP_CONFIG", "IQIDDET/models/fclip_config.yaml"),
        fclip_params=os.environ.get("FCLIP_PARAMS", "IQIDDET/params.yaml"),
        fclip_device=None,
        ocr_device="gpu" if _cuda_available else "cpu",
        ocr_det_model_name="PP-OCRv5_server_det",
        ocr_det_model_dir=os.environ.get("OCR_DET_MODEL_DIR", "IQIDDET/models/PP-OCRv5_server_det"),
        ocr_det_limit_side_len=960,
        ocr_det_limit_type="max",
        ocr_rec_model_name="en_PP-OCRv5_mobile_rec",
        ocr_rec_model_dir=os.environ.get("OCR_REC_MODEL_DIR", "IQIDDET/models/OCR_rec_inference_best_accuracy0325"),
        enable_ocr_orientation=True,
        ocr_orientation_model=os.environ.get("OCR_ORIENTATION_MODEL", "IQIDDET/models/ocr_orientation_model.pth"),
        ocr_orientation_device="cuda:0" if _cuda_available else "cpu",
        ocr_number_range="1-19",
    )

    # Align default path semantics with the CLI script.
    args.location_model = args.location_model or rip.DEFAULT_LOCATION_MODEL_PATH
    args.location2_model = args.location2_model or rip.DEFAULT_LOCATION1_MODEL_PATH
    return args


def _build_runtime_signature(args: argparse.Namespace) -> Tuple[Any, ...]:
    """Only values that impact heavy model initialization belong in the signature."""
    return (
        args.mode,
        args.roi_weights,
        round(float(args.primary_conf), 6),
        args.primary_weights,
        args.device,
        args.det_device,
        bool(args.wide_slice),
        bool(args.enable_correction),
        args.correction_model,
        bool(args.enable_location),
        args.location_model,
        round(float(args.location_conf), 6),
        bool(args.enable_location2),
        args.location2_model,
        round(float(args.location2_conf), 6),
        bool(args.enable_iqi),
        args.gauge_weights,
        args.fclip_ckpt,
        args.fclip_config,
        args.fclip_params,
        args.gauge_device,
        args.ocr_device,
        args.ocr_det_model_name,
        args.ocr_det_model_dir,
        args.ocr_rec_model_name,
        args.ocr_rec_model_dir,
        bool(args.enable_ocr_orientation),
        args.ocr_orientation_model,
        args.ocr_orientation_device,
        args.ocr_number_range,
    )


def _write_progress_file(output_dir: Path, current: int, total: int, last_file: Optional[str], stage: str) -> None:
    progress_file = output_dir / "progress.json"
    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "current": int(current),
                    "total": int(total),
                    "last_file": last_file,
                    "stage": stage,
                },
                f,
                ensure_ascii=False,
            )
    except Exception:
        pass


def _create_runtime_bundle(args: argparse.Namespace) -> Dict[str, Any]:
    rip = _load_weld_pipeline_module()

    roi_detector = rip.build_roi_detector(args)
    if args.mode in {"seg", "det"} and roi_detector is None:
        raise ValueError(f"{args.mode} 模式必须提供 --roi-weights 以执行ROI检测")

    font_renderer = rip.FontRenderer(font_path=args.font_path, font_size=args.font_size)

    corrector = None
    if args.enable_correction:
        print(f"[runtime] 启用焊缝底片方向矫正,模型路径: {args.correction_model}")
        corrector = rip.WeldOrientationCorrector(
            model_path=args.correction_model,
            model_type="resnet50",
        )

    locator = None
    if args.enable_location:
        print(f"[runtime] 启用焊缝位置检测，模型路径: {args.location_model}")
        locator = rip.WeldSeamLocator(
            model_path=str(Path(args.location_model)),
            conf_threshold=args.location_conf,
        )

    detector = None
    if args.enable_location2:
        print(f"[runtime] 启用缺陷位置检测2，模型路径: {args.location2_model}")
        detector = rip.WeldDefectPositionDetector(
            model_path=str(Path(args.location2_model)),
            conf_threshold=args.location2_conf,
        )

    iqi_inferencer = None
    if args.enable_iqi:
        if not rip._IQI_AVAILABLE:
            print(
                "[runtime] [警告] IQIInferencer 不可用，跳过 IQI 推理: "
                f"{getattr(rip, '_IQI_IMPORT_ERROR', 'unknown import error')}"
            )
        else:
            print("[runtime] 启用 IQI 像质计识别（常驻复用）")

            def _abs(p: Optional[str]) -> Optional[str]:
                return str(Path(p).resolve()) if p else p

            try:
                iqi_inferencer = rip.IQIInferencer(
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
                    ocr_rec_model_name=args.ocr_rec_model_name,
                    ocr_rec_model_dir=_abs(args.ocr_rec_model_dir),
                    ocr_det_limit_side_len=args.ocr_det_limit_side_len,
                    ocr_det_limit_type=args.ocr_det_limit_type,
                    enable_ocr_orientation=args.enable_ocr_orientation,
                    ocr_orientation_model=_abs(args.ocr_orientation_model),
                    ocr_orientation_device=args.ocr_orientation_device,
                    ocr_number_range=args.ocr_number_range,
                    fclip_device=args.fclip_device,
                    fclip_model_config=_abs(args.fclip_config),
                    fclip_params=_abs(args.fclip_params),
                )
            except Exception as iqi_init_err:
                print(f"[runtime] [警告] IQIInferencer 初始化失败，跳过 IQI 推理: {iqi_init_err}")

    runner = rip.InferencePipelineRunner(
        args=args,
        roi_detector=roi_detector,
        font_renderer=font_renderer,
        debug_root=None,
        corrector=corrector,
        locator=locator,
        detector=detector,
        iqi_inferencer=iqi_inferencer,
    )

    return {
        "args": args,
        "runner": runner,
        "roi_detector": roi_detector,
        "font_renderer": font_renderer,
        "corrector": corrector,
        "locator": locator,
        "detector": detector,
        "iqi_inferencer": iqi_inferencer,
    }


def _get_or_create_runtime_bundle(args: argparse.Namespace) -> Dict[str, Any]:
    signature = _build_runtime_signature(args)
    with _runtime_cache_lock:
        bundle = _runtime_cache.get(signature)
        if bundle is not None:
            return bundle
        print(f"[runtime] creating model bundle for signature={signature}")
        bundle = _create_runtime_bundle(args)
        _runtime_cache[signature] = bundle
        return bundle


class InferenceResponse(BaseModel):
    """推理响应"""
    task_id: str
    status: str
    message: str


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int = 0
    total: int = 0
    current_file: Optional[str] = None
    stage: Optional[str] = None
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    torch_available: bool
    cuda_available: bool
    cuda_device_count: int = 0
    cuda_device_name: Optional[str] = None


# ==============================================================================
# API 端点
# ==============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    cuda_device_count = 0
    cuda_device_name = None
    
    if _torch_available and _cuda_available:
        import torch
        cuda_device_count = torch.cuda.device_count()
        if cuda_device_count > 0:
            cuda_device_name = torch.cuda.get_device_name(0)

    if (
        INFERENCE_EXECUTION_MODE not in {"subprocess", "script"}
        and INFERENCE_PREWARM_ENABLED
        and INFERENCE_HEALTH_REQUIRES_WARMUP
        and not _runtime_warmup_completed
    ):
        detail = "Inference runtime is still warming up"
        if _runtime_warmup_error:
            detail = f"Inference runtime warmup failed: {_runtime_warmup_error}"
        raise HTTPException(status_code=503, detail=detail)
    
    return HealthResponse(
        status="healthy",
        torch_available=_torch_available,
        cuda_available=_cuda_available,
        cuda_device_count=cuda_device_count,
        cuda_device_name=cuda_device_name
    )


@app.get("/")
async def root():
    """根路径"""
    return {"service": "AIVision Inference Service", "version": "1.0.0"}


@app.post("/thumbnail/convert")
async def convert_thumbnail(
    file: UploadFile = FastAPIFile(...),
    quality: int = Form(85),
):
    """将 TIFF/DICOM 原图同步转换为 JPEG 缩略图字节流。"""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="上传文件为空")

        safe_quality = max(1, min(100, int(quality)))
        jpeg_bytes = _convert_to_thumbnail_jpeg(content, file.filename or "", safe_quality)
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"缩略图转换失败: {exc}") from exc


@app.post("/thumbnail/convert-path")
async def convert_thumbnail_from_path(
    path: str = Form(...),
    filename: str = Form(""),
    quality: int = Form(85),
):
    """从共享数据卷路径读取 TIFF/DICOM 原图并同步转换为 JPEG 缩略图字节流。"""
    try:
        source_path = Path(path).resolve()
        allowed_roots = [
            Path(os.environ.get("STORAGE_LOCAL_BASE_DIR", "/app/data/files")).resolve(),
            Path("/app/data/files").resolve(),
        ]
        if not any(source_path == root or root in source_path.parents for root in allowed_roots):
            raise HTTPException(status_code=400, detail="缩略图源文件路径不在允许的数据目录内")
        if not source_path.exists() or not source_path.is_file():
            raise HTTPException(status_code=404, detail="缩略图源文件不存在")

        content = source_path.read_bytes()
        if not content:
            raise HTTPException(status_code=400, detail="源文件为空")

        safe_quality = max(1, min(100, int(quality)))
        jpeg_bytes = _convert_to_thumbnail_jpeg(content, filename or source_path.name, safe_quality)
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"缩略图转换失败: {exc}") from exc


@app.post("/inference/submit", response_model=InferenceResponse)
async def submit_inference(request: InferenceRequest, background_tasks: BackgroundTasks):
    """
    提交推理任务
    
    任务将在后台异步执行，可通过 /inference/{task_id}/status 查询进度
    """
    task_id = request.task_id
    
    # 检查任务是否已存在
    if task_id in inference_tasks and inference_tasks[task_id]["status"] == "processing":
        raise HTTPException(status_code=409, detail=f"Task {task_id} is already processing")
    
    # 初始化任务状态
    inference_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "total": len(request.file_paths),
        "current_file": None,
        "stage": "accepted",
        "error_message": None,
        "start_time": time.time()
    }

    # 清理旧的进度文件和结果文件
    output_dir = Path(f"/app/data/results/{task_id}")
    if output_dir.exists():
        import shutil
        try:
            # 删除目录下的关键文件，而不是删除整个目录（防止权限问题）
            for f in output_dir.glob("*"):
                if f.is_file():
                    f.unlink()
            print(f"Cleaned up old results for task {task_id}")
        except Exception as e:
            print(f"Warning: Failed to clean up old results for task {task_id}: {e}")

    _write_progress_file(
        output_dir=output_dir,
        current=0,
        total=len(request.file_paths),
        last_file=None,
        stage="accepted",
    )
    print(f"[Task {task_id}] Progress initialized: 0/{len(request.file_paths)} stage=accepted")

    # 在后台执行推理
    background_tasks.add_task(run_inference_task, request)
    
    return InferenceResponse(
        task_id=task_id,
        status="accepted",
        message=f"Inference task submitted with {len(request.file_paths)} files"
    )


@app.get("/inference/{task_id}/status", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询推理任务状态"""
    if task_id not in inference_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = inference_tasks[task_id]
    
    # 尝试从 progress.json 读取最新进度
    progress_file = Path(f"/app/data/results/{task_id}/progress.json")
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
                # 字段名与 run_inference_pipeline.py 中 _update_progress 输出一致
                task["progress"] = progress_data.get("current", task["progress"])
                task["current_file"] = progress_data.get("last_file", task.get("current_file"))
                task["stage"] = progress_data.get("stage", task.get("stage"))
        except:
            pass
    
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        total=task["total"],
        current_file=task.get("current_file"),
        stage=task.get("stage"),
        error_message=task.get("error_message")
    )


@app.get("/inference/{task_id}/result")
async def get_task_result(task_id: str):
    """获取推理结果"""
    if task_id not in inference_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = inference_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Task is not completed. Current status: {task['status']}"
        )
    
    # 读取结果文件
    result_path = Path(f"/app/data/results/{task_id}/inference_results.json")
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    with open(result_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.delete("/inference/{task_id}")
async def cancel_task(task_id: str):
    """取消/清理任务"""
    if task_id in inference_tasks:
        del inference_tasks[task_id]
    return {"message": f"Task {task_id} cleaned up"}


# ==============================================================================
# OCR 区域识别（同步，供前端框选功能使用）
# ==============================================================================

_IQIDDET_ROOT = PROJECT_ROOT / "IQIDDET"
_IQIDDET_SRC_ROOT = _IQIDDET_ROOT / "src"
for _iqi_import_path in (str(_IQIDDET_SRC_ROOT), str(_IQIDDET_ROOT)):
    if _iqi_import_path in sys.path:
        sys.path.remove(_iqi_import_path)
sys.path[:0] = [str(_IQIDDET_SRC_ROOT), str(_IQIDDET_ROOT)]

from gauge.app.region_ocr_api import (
    RecognizeRequest as _BaseRecognizeRequest,
    RecognizeResponse,
    close_region_ocr_api,
    recognize_region as _recognize_region,
    init_region_ocr_api,
)
from gauge.app.region_snr_api import (
    SNRRequest as _BaseSNRRequest,
    SNRResponse,
    close_region_snr_api,
    compute_region_snr as _compute_region_snr,
    init_region_snr_api,
)
from gauge.app.double_wire_api import (
    DoubleWireRequest as _BaseDoubleWireRequest,
    DoubleWireResponse,
    close_double_wire_api,
    compute_double_wire as _compute_double_wire,
    init_double_wire_api,
)


class RecognizeRequest(_BaseRecognizeRequest):
    """扩展的 OCR 识别请求，增加调试上下文字段。"""
    task_id: Optional[str] = Field(default=None, description="任务ID，用于调试图片文件命名")
    field_name: Optional[str] = Field(default=None, description="识别字段名称，如 film_no、weld_no 等")


class RegionSNRRequest(_BaseSNRRequest):
    """扩展的区域归一化信噪比请求，增加调试上下文字段。"""
    task_id: Optional[str] = Field(default=None, description="任务ID，用于调试图片文件命名")
    field_name: Optional[str] = Field(default=None, description="识别字段名称，如 normalizedSnr")


class DoubleWireAnalysisRequest(_BaseDoubleWireRequest):
    """扩展的双丝分辨率分析请求，增加调试上下文字段。"""
    task_id: Optional[str] = Field(default=None, description="任务ID，用于调试图片文件命名")
    field_name: Optional[str] = Field(default=None, description="识别字段名称，如 doubleWireResolution")


# 调试图片存储目录
_OCR_DEBUG_DIR = Path("/app/data/results/ocr_debug")
_DOUBLE_WIRE_DEBUG_DIR = Path("/app/data/results/doubleWire_debug")
_DEBUG_IMAGE_RETENTION_DAYS = 7


def _get_positive_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        print(f"[OCR debug] 环境变量 {name}={raw_value!r} 非法，回退到默认值 {default}")
        return default


_DEBUG_IMAGE_CLEANUP_INTERVAL_SECONDS = _get_positive_int_env(
    "OCR_DEBUG_CLEANUP_INTERVAL_SECONDS",
    24 * 60 * 60,
)


def _save_debug_image(
    image_base64: str,
    task_id: Optional[str],
    field_name: Optional[str],
    debug_dir: Path,
    log_prefix: str,
) -> None:
    """将 base64 图片保存为 PNG 文件，用于后期分析。"""
    import base64
    import re
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)

        # 去除 data URL 前缀
        b64_data = str(image_base64 or "")
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]

        img_bytes = base64.b64decode(b64_data)

        # 构造文件名：时间戳_taskid_fieldname.png
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_task = re.sub(r"[^\w-]", "_", task_id or "unknown")
        safe_field = re.sub(r"[^\w-]", "_", field_name or "field")
        filename = f"{ts}_{safe_task}_{safe_field}.png"
        out_path = debug_dir / filename

        # 验证并重新编码为 PNG（确保格式正确）
        import numpy as np
        import cv2
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            cv2.imwrite(str(out_path), img)
            print(f"[{log_prefix} debug] 已保存调试图片: {out_path}")
        else:
            # 解码失败时直接写入原始字节
            out_path.write_bytes(img_bytes)
            print(f"[{log_prefix} debug] 已保存原始调试图片（解码异常）: {out_path}")
    except Exception as exc:
        print(f"[{log_prefix} debug] 保存调试图片失败（不影响识别结果）: {exc}")


def _save_ocr_debug_image(image_base64: str, task_id: Optional[str], field_name: Optional[str]) -> None:
    """将 OCR / SNR 框选的 base64 图片保存为 PNG 文件，用于后期分析。"""
    _save_debug_image(image_base64, task_id, field_name, _OCR_DEBUG_DIR, "OCR")


def _save_double_wire_debug_image(image_base64: str, task_id: Optional[str], field_name: Optional[str]) -> None:
    """将双丝分辨率分析的 base64 图片保存为 PNG 文件，用于后期分析。"""
    _save_debug_image(image_base64, task_id, field_name, _DOUBLE_WIRE_DEBUG_DIR, "doubleWire")


def _cleanup_debug_images() -> None:
    """清理超过 {_DEBUG_IMAGE_RETENTION_DAYS} 天的调试图片。"""
    try:
        cutoff = time.time() - _DEBUG_IMAGE_RETENTION_DAYS * 86400
        removed = 0
        for debug_dir in (_OCR_DEBUG_DIR, _DOUBLE_WIRE_DEBUG_DIR):
            if not debug_dir.exists():
                continue
            for f in debug_dir.glob("*.png"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
        if removed:
            print(f"[debug image] 已清理 {removed} 张超过 {_DEBUG_IMAGE_RETENTION_DAYS} 天的调试图片")
    except Exception as exc:
        print(f"[debug image] 清理调试图片失败: {exc}")


async def _periodic_debug_image_cleanup() -> None:
    """后台定时清理 OCR / 双丝分辨率调试图片。"""
    loop = asyncio.get_running_loop()
    interval = _DEBUG_IMAGE_CLEANUP_INTERVAL_SECONDS
    print(
        f"[debug image] 定时清理任务已启动: interval={interval}s, retention={_DEBUG_IMAGE_RETENTION_DAYS}d"
    )
    try:
        await loop.run_in_executor(None, _cleanup_debug_images)
        while True:
            await asyncio.sleep(interval)
            await loop.run_in_executor(None, _cleanup_debug_images)
    except asyncio.CancelledError:
        print("[debug image] 定时清理任务已停止")
        raise


def _abs_model_path(rel_or_abs: str) -> str:
    """将相对路径解析为基于 PROJECT_ROOT 的绝对路径，绝对路径原样返回。"""
    p = Path(rel_or_abs)
    if p.is_absolute():
        return str(p)
    return str(PROJECT_ROOT / rel_or_abs)


def _init_ocr_cpu() -> None:
    """以 CPU 模式初始化区域 OCR，使用 env var 中的模型路径（解析为绝对路径）。"""
    det_model_dir = _abs_model_path(
        os.environ.get("OCR_DET_MODEL_DIR", "IQIDDET/models/PP-OCRv5_server_det")
    )
    rec_model_dir = _abs_model_path(
        os.environ.get("OCR_REC_MODEL_DIR", "IQIDDET/models/OCR_rec_inference_best_accuracy0325")
    )
    orientation_model = _abs_model_path(
        os.environ.get("OCR_ORIENTATION_MODEL", "IQIDDET/models/ocr_orientation_model.pth")
    )
    print(f"[OCR init] det_model_dir={det_model_dir}")
    print(f"[OCR init] rec_model_dir={rec_model_dir}")
    print(f"[OCR init] orientation_model={orientation_model}")
    init_region_ocr_api(
        ocr_det_model_dir=det_model_dir,
        ocr_rec_model_dir=rec_model_dir,
        ocr_device="cpu",
        ocr_orientation_model=orientation_model,
    )


@app.post("/inference/recognize", response_model=RecognizeResponse)
async def recognize_region_endpoint(request: RecognizeRequest):
    """同步识别单张图片区域（base64输入），用于前端实时OCR框选功能。"""
    import gauge.app.region_ocr_api as _ocr_mod
    # 若 warmup 尚未完成，保证懒加载时也使用 CPU，不触发默认的 gpu 初始化
    if _ocr_mod._region_ocr_service is None:
        _init_ocr_cpu()

    # 保存调试图片（异步、非阻塞；失败不影响识别结果）
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _save_ocr_debug_image,
        request.image_base64,
        request.task_id,
        request.field_name,
    )

    # 构造基础请求（只传 image_base64，避免底层 model 字段校验问题）
    from gauge.app.region_ocr_api import RecognizeRequest as _BaseReq
    base_req = _BaseReq(image_base64=request.image_base64)
    return await _recognize_region(base_req)


@app.post("/inference/region-snr", response_model=SNRResponse)
async def compute_region_snr_endpoint(request: RegionSNRRequest):
    """同步计算单张图片区域的归一化信噪比（base64输入），用于前端实时框选功能。"""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _save_ocr_debug_image,
        request.image_base64,
        request.task_id,
        request.field_name or "normalizedSnr",
    )

    base_req = _BaseSNRRequest(image_base64=request.image_base64)
    return await _compute_region_snr(base_req)


@app.post("/inference/double-wire", response_model=DoubleWireResponse)
async def compute_double_wire_endpoint(request: DoubleWireAnalysisRequest):
    """同步分析双丝像质计 strip 图像（base64输入），用于前端双丝分辨率手动选择。"""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _save_double_wire_debug_image,
        request.image_base64,
        request.task_id,
        request.field_name or "doubleWireResolution",
    )

    base_req = _BaseDoubleWireRequest(image_base64=request.image_base64)
    return await _compute_double_wire(base_req)


# ==============================================================================
# 推理执行逻辑 - 调用 run_inference_pipeline.py 脚本
# ==============================================================================

async def run_inference_task(request: InferenceRequest):
    """执行推理任务"""
    task_id = request.task_id
    
    try:
        inference_tasks[task_id]["status"] = "processing"
        
        # 在线程池中执行同步推理代码
        loop = asyncio.get_event_loop()
        runner_func = (
            _sync_run_inference_via_script
            if INFERENCE_EXECUTION_MODE in {"subprocess", "script"}
            else _sync_run_inference_direct
        )
        await loop.run_in_executor(executor, runner_func, request)
        
        inference_tasks[task_id]["status"] = "completed"
        inference_tasks[task_id]["progress"] = inference_tasks[task_id]["total"]
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Inference failed for task {task_id}: {error_msg}")
        inference_tasks[task_id]["status"] = "failed"
        inference_tasks[task_id]["error_message"] = str(e)


def _sync_run_inference_direct(request: InferenceRequest):
    """Execute inference in-process and reuse loaded models across tasks."""
    rip = _load_weld_pipeline_module()

    task_id = request.task_id
    file_paths = request.file_paths
    output_dir = Path(f"/app/data/results/{task_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    file_list_path = output_dir / "input_files.txt"
    absolute_paths: List[str] = []
    for rel_path in file_paths:
        cleaned = rel_path[1:] if rel_path.startswith("/") else rel_path
        full_path = Path("/app/data/files") / cleaned
        absolute_paths.append(str(full_path))

    with open(file_list_path, "w", encoding="utf-8") as f:
        f.write("\n".join(absolute_paths))

    print(f"[Task {task_id}] Created file list with {len(absolute_paths)} files")
    inference_tasks[task_id]["stage"] = "initializing"
    _write_progress_file(output_dir, 0, len(absolute_paths), None, "initializing")
    print(f"[Task {task_id}] Progress updated: 0/{len(absolute_paths)} stage=initializing")

    args = _build_runtime_args(request, output_dir, file_list_path)
    print(
        f"[Task {task_id}] Runtime config: mode={args.mode}, wide_slice={args.wide_slice}, "
        f"enable_location={args.enable_location}, enable_location2={args.enable_location2}, enable_iqi={args.enable_iqi}"
    )
    bundle = _get_or_create_runtime_bundle(args)
    runner = bundle["runner"]

    # Runner holds task-scoped mutable fields, so execution is serialized here.
    with _runtime_execution_lock:
        runner.args = args
        runner.output_dir = output_dir
        runner.iqi_image_root = Path(args.image_dir).resolve() if args.image_dir else None
        runner.iqi_vis_dir = (
            output_dir / "iqi_vis"
            if output_dir is not None and runner.iqi_inferencer is not None
            else None
        )
        runner.debug_root = (output_dir / "temp") if getattr(rip, "DEBUG_STEP", False) else None
        if runner.debug_root is not None:
            runner.debug_root.mkdir(parents=True, exist_ok=True)

        image_paths = rip.collect_images(None, file_list_path, args.max_images)
        prepared_root = output_dir / "prepared_inputs"
        image_inputs = [rip._prepare_image_input(path, prepared_root) for path in image_paths]
        inference_tasks[task_id]["stage"] = "running"
        _write_progress_file(output_dir, 0, len(image_inputs), None, "running")
        print(f"[Task {task_id}] Progress updated: 0/{len(image_inputs)} stage=running")

        log_prefix = f"[Task {task_id}] "
        with redirect_stdout(_PrefixedStream(log_prefix, sys.stdout)), redirect_stderr(
            _PrefixedStream(log_prefix, sys.stderr)
        ):
            results = runner.run(image_inputs)

        results_path = output_dir / args.results_json
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump({"mode": args.mode, "results": results}, f, indent=2, ensure_ascii=False)

        print(f"[Task {task_id}] 推理完成: 模式={args.mode}，共处理 {len(results)} 张图像。")
        print(f"[Task {task_id}] 结果JSON: {results_path}")

        if args.enable_iqi:
            iqi_out_path = output_dir / args.iqi_results_json
            if not rip._IQI_AVAILABLE:
                with open(iqi_out_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "ok": False,
                            "fatal_error": getattr(rip, "_IQI_IMPORT_ERROR", "unknown import error"),
                            "results": [],
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
                print(f"[Task {task_id}] [警告] IQI 模块不可用，已写入错误占位: {iqi_out_path}")
            else:
                iqi_raw_records = [r.get("ocr") for r in results if r.get("ocr") is not None]
                delivery_records = [rip.build_delivery_record(rec) for rec in iqi_raw_records]
                summary = rip.build_iqi_statistics(iqi_raw_records)
                image_root = Path(args.image_dir).resolve() if args.image_dir else None
                payload = {
                    "schema": "iqi_grade_batch_v1",
                    "ok": True,
                    "fatal_error": None,
                    "meta": {
                        "created_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                        "image_root": str(image_root) if image_root is not None else None,
                        **(
                            runner.iqi_inferencer.get_runtime_meta()
                            if runner.iqi_inferencer is not None
                            else {}
                        ),
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
                        "vis_dir": "iqi_vis" if runner.iqi_inferencer is not None else None,
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
                with open(iqi_out_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                print(f"[Task {task_id}] IQI 推理完成: 共处理 {len(delivery_records)} 张图像，结果JSON: {iqi_out_path}")

        if not results_path.exists():
            raise RuntimeError("Inference completed but result file not found")


def _sync_run_inference_via_script(request: InferenceRequest):
    """
    通过调用 run_inference_pipeline.py 脚本执行推理
    这样可以复用完整的推理逻辑，包括 --det-wide-slice 等高级功能
    """
    task_id = request.task_id
    file_paths = request.file_paths
    
    # 准备输出目录
    output_dir = Path(f"/app/data/results/{task_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 准备文件列表
    file_list_path = output_dir / "input_files.txt"
    absolute_paths = []
    for rel_path in file_paths:
        if rel_path.startswith("/"):
            rel_path = rel_path[1:]
        full_path = Path("/app/data/files") / rel_path
        absolute_paths.append(str(full_path))
    
    with open(file_list_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(absolute_paths))
    
    print(f"[Task {task_id}] Created file list with {len(absolute_paths)} files")
    
    # 获取模型权重路径
    roi_weights = request.roi_weights or os.environ.get(
        "ROI_WEIGHTS", "/app/model/weights/weldROI4.pt"
    )
    primary_weights = request.primary_weights or os.environ.get(
        "PRIMARY_WEIGHTS", "/app/model/weights/primary-weights.pth"
    )
    device = request.device if _cuda_available else "cpu"
    
    # 构建命令
    script_path = PROJECT_ROOT / "run_inference_pipeline.py"
    cmd = [
        sys.executable,  # python3
        str(script_path),
        "--file-list", str(file_list_path),
        "--output-dir", str(output_dir),
        "--results-json", "inference_results.json",
        "--mode", request.mode,
        "--roi-weights", roi_weights,
        "--primary-weights", primary_weights,
        "--primary-conf", str(request.primary_conf),
        "--device", device,
        "--det-device", device,
    ]
    
    # 添加 --wide-slice 参数
    if request.wide_slice:
        cmd.append("--wide-slice")
    
    # 自动检测矫正模型，存在则启用方向矫正预处理
    correction_model = os.environ.get(
        "CORRECTION_MODEL", "/app/model/weights/weld_orientation_model.pth"
    )
    if os.path.exists(correction_model):
        cmd += ["--enable-correction", "--correction-model", correction_model]
        print(f"[Task {task_id}] 矫正模型已预设，启用方向矫正: {correction_model}")
    else:
        print(f"[Task {task_id}] 矫正模型未找到，跳过方向矫正: {correction_model}")

    # 焊缝位置检测逻辑（B路径，location_0.pt）
    if request.enable_location:
        location_model = os.environ.get(
            "LOCATION_MODEL", "/app/model/weights/location_0.pt"
        )
        if os.path.exists(location_model):
            cmd += [
                "--enable-location",
                "--location-model", location_model,
                "--location-conf", str(request.location_conf)
            ]
            print(f"[Task {task_id}] 位置检测模型已预设，启用位置检测: {location_model}")
        else:
            print(f"[Task {task_id}] 位置检测模型未找到，跳过位置检测: {location_model}")

    # 缺陷位置检测2逻辑（D路径，location_1.pt）
    if request.enable_location2:
        location2_model = os.environ.get(
            "LOCATION2_MODEL", "/app/model/weights/location_1.pt"
        )
        if os.path.exists(location2_model):
            cmd += [
                "--enable-location2",
                "--location2-model", location2_model,
                "--location2-conf", str(request.location2_conf)
            ]
            print(f"[Task {task_id}] 缺陷位置检测2模型已预设，启用检测: {location2_model}")
        else:
            print(f"[Task {task_id}] 缺陷位置检测2模型未找到，跳过检测: {location2_model}")

    # IQI 像质计识别
    if request.enable_iqi:
        iqi_device = "cuda:0" if _cuda_available else "cpu"
        cmd += [
            "--enable-iqi",
            "--gauge-weights",        os.environ.get("GAUGE_WEIGHTS",        "IQIDDET/models/guagerotation.pt"),
            "--fclip-ckpt",           os.environ.get("FCLIP_CKPT",           "IQIDDET/models/fclip67.pth.tar"),
            "--fclip-config",         os.environ.get("FCLIP_CONFIG",         "IQIDDET/models/fclip_config.yaml"),
            "--fclip-params",         os.environ.get("FCLIP_PARAMS",         "IQIDDET/params.yaml"),
            "--ocr-rec-model-dir",    os.environ.get("OCR_REC_MODEL_DIR",    "IQIDDET/models/OCR_rec_inference_best_accuracy0325"),
            "--ocr-det-model-dir",    os.environ.get("OCR_DET_MODEL_DIR",    "IQIDDET/models/PP-OCRv5_server_det"),
            "--enable-ocr-orientation",
            "--ocr-orientation-model", os.environ.get("OCR_ORIENTATION_MODEL", "IQIDDET/models/ocr_orientation_model.pth"),
            "--ocr-orientation-device", iqi_device,
            "--ocr-device",           "gpu" if _cuda_available else "cpu",
            "--ocr-number-range",     "1-19",
        ]
        print(f"[Task {task_id}] 启用IQI像质计识别 (device={iqi_device})")
    else:
        print(f"[Task {task_id}] IQI像质计识别未启用")

    print(f"[Task {task_id}] Executing command: {' '.join(cmd)}")
    
    # 执行脚本
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(PROJECT_ROOT)
        )
        
        # 实时读取输出
        for line in process.stdout:
            line = line.strip()
            if line:
                print(f"[Task {task_id}] {line}")
        
        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"Inference script exited with code {process.returncode}")
        
        # 验证结果文件存在
        result_file = output_dir / "inference_results.json"
        if not result_file.exists():
            raise RuntimeError("Inference completed but result file not found")
        
        print(f"[Task {task_id}] Inference completed successfully")
        
    except Exception as e:
        print(f"[Task {task_id}] Error: {e}")
        raise


# ==============================================================================
# 启动事件
# ==============================================================================

async def _warmup_ocr():
    """后台初始化 OCR 服务，避免首次请求延迟（不阻塞 health check）"""
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        print("[OCR warmup] 开始初始化 OCR 服务 (CPU 模式)...")
        await loop.run_in_executor(None, _init_ocr_cpu)
        print("[OCR warmup] OCR 服务初始化完成")
    except Exception as e:
        print(f"[OCR warmup] OCR 服务初始化失败（首次请求时将重试）: {e}")


def _build_default_warmup_request() -> InferenceRequest:
    return InferenceRequest(
        task_id="__warmup__",
        file_paths=[],
        mode=os.environ.get("INFERENCE_MODE", "det"),
        device=os.environ.get("INFERENCE_DEVICE", "cuda:0"),
        roi_weights=os.environ.get("ROI_WEIGHTS", "/app/model/weights/weldROI4.pt"),
        primary_weights=os.environ.get("PRIMARY_WEIGHTS", "/app/model/weights/primary-weights.pth"),
        primary_conf=float(os.environ.get("PRIMARY_CONF", "0.15")),
        wide_slice=os.environ.get("WIDE_SLICE", "true").strip().lower() not in {"0", "false", "no", "off"},
        enable_location=os.environ.get("ENABLE_LOCATION", "true").strip().lower() not in {"0", "false", "no", "off"},
        location_conf=float(os.environ.get("LOCATION_CONF", "0.6")),
        enable_location2=os.environ.get("ENABLE_LOCATION2", "true").strip().lower() not in {"0", "false", "no", "off"},
        location2_conf=float(os.environ.get("LOCATION2_CONF", "0.25")),
        enable_iqi=os.environ.get("ENABLE_IQI", "true").strip().lower() not in {"0", "false", "no", "off"},
    )


def _prewarm_default_runtime() -> None:
    global _runtime_warmup_completed, _runtime_warmup_error
    if INFERENCE_EXECUTION_MODE in {"subprocess", "script"}:
        print("[runtime warmup] 当前为 subprocess 模式，跳过常驻模型预热")
        _runtime_warmup_completed = True
        _runtime_warmup_error = None
        return
    output_dir = Path("/app/data/results/__warmup__")
    output_dir.mkdir(parents=True, exist_ok=True)
    file_list_path = output_dir / "input_files.txt"
    file_list_path.write_text("", encoding="utf-8")
    request = _build_default_warmup_request()
    args = _build_runtime_args(request, output_dir, file_list_path)
    _get_or_create_runtime_bundle(args)
    _runtime_warmup_completed = True
    _runtime_warmup_error = None
    print("[runtime warmup] 默认推理模型预热完成")


async def _warmup_inference_runtime():
    global _runtime_warmup_error
    loop = asyncio.get_event_loop()
    try:
        print("[runtime warmup] 开始预热默认推理模型...")
        await loop.run_in_executor(None, _prewarm_default_runtime)
    except Exception as e:
        _runtime_warmup_error = str(e)
        print(f"[runtime warmup] 默认推理模型预热失败（首次任务时将重试）: {e}")


@app.on_event("startup")
async def startup_event():
    """服务启动时的初始化"""
    import asyncio
    print("=" * 60)
    print("AIVision Inference Service Starting...")
    print(f"PyTorch available: {_torch_available}")
    print(f"CUDA available: {_cuda_available}")
    if _cuda_available:
        import torch
        print(f"CUDA device count: {torch.cuda.device_count()}")
        if torch.cuda.device_count() > 0:
            print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
    primary_weights = os.environ.get("PRIMARY_WEIGHTS", "/app/model/weights/primary-weights.pth")
    print(f"Primary weights: {primary_weights}")
    print("=" * 60)
    print(f"Inference execution mode: {INFERENCE_EXECUTION_MODE}")
    print(f"Inference prewarm enabled: {INFERENCE_PREWARM_ENABLED}")
    print(f"Inference health requires warmup: {INFERENCE_HEALTH_REQUIRES_WARMUP}")
    init_region_snr_api()
    print("[SNR init] 区域 SNR 服务初始化完成")
    init_double_wire_api()
    print("[double-wire init] 双丝分辨率服务初始化完成")
    # 后台预热 OCR，不阻塞 health check
    app.state.ocr_warmup_task = asyncio.create_task(_warmup_ocr())
    app.state.inference_warmup_task = (
        asyncio.create_task(_warmup_inference_runtime())
        if INFERENCE_PREWARM_ENABLED
        else None
    )
    app.state.debug_image_cleanup_task = asyncio.create_task(_periodic_debug_image_cleanup())


@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时释放后台任务和 OCR / SNR / double-wire 资源。"""
    for task_name in ("ocr_warmup_task", "inference_warmup_task", "debug_image_cleanup_task"):
        task = getattr(app.state, task_name, None)
        if task is None:
            continue
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"[shutdown] 关闭后台任务 {task_name} 失败: {exc}")
        finally:
            setattr(app.state, task_name, None)
    close_region_ocr_api()
    close_region_snr_api()
    close_double_wire_api()
    for bundle in _runtime_cache.values():
        iqi_inferencer = bundle.get("iqi_inferencer")
        if iqi_inferencer is not None:
            try:
                iqi_inferencer.close()
            except Exception as exc:
                print(f"[shutdown] 关闭 IQI 常驻推理器失败: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
