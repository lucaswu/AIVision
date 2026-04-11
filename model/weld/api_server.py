#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIVision 推理服务 API 入口
提供 HTTP 接口调用焊缝检测模型

启动方式：
    uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import json
import os
import subprocess
import sys
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, BackgroundTasks
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
        except:
            pass
    
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        total=task["total"],
        current_file=task.get("current_file"),
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
if str(_IQIDDET_ROOT) not in sys.path:
    sys.path.insert(0, str(_IQIDDET_ROOT))

from gauge.region_ocr_api import (
    RecognizeRequest as _BaseRecognizeRequest,
    RecognizeResponse,
    close_region_ocr_api,
    recognize_region as _recognize_region,
    init_region_ocr_api,
)


class RecognizeRequest(_BaseRecognizeRequest):
    """扩展的 OCR 识别请求，增加调试上下文字段。"""
    task_id: Optional[str] = Field(default=None, description="任务ID，用于调试图片文件命名")
    field_name: Optional[str] = Field(default=None, description="识别字段名称，如 film_no、weld_no 等")


# OCR 调试图片存储目录
_OCR_DEBUG_DIR = Path("/app/data/results/ocr_debug")
_OCR_DEBUG_RETENTION_DAYS = 7


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


_OCR_DEBUG_CLEANUP_INTERVAL_SECONDS = _get_positive_int_env(
    "OCR_DEBUG_CLEANUP_INTERVAL_SECONDS",
    24 * 60 * 60,
)


def _save_ocr_debug_image(image_base64: str, task_id: Optional[str], field_name: Optional[str]) -> None:
    """将 OCR 框选的 base64 图片保存为 PNG 文件，用于后期分析。"""
    import base64
    import re
    try:
        _OCR_DEBUG_DIR.mkdir(parents=True, exist_ok=True)

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
        out_path = _OCR_DEBUG_DIR / filename

        # 验证并重新编码为 PNG（确保格式正确）
        import numpy as np
        import cv2
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            cv2.imwrite(str(out_path), img)
            print(f"[OCR debug] 已保存调试图片: {out_path}")
        else:
            # 解码失败时直接写入原始字节
            out_path.write_bytes(img_bytes)
            print(f"[OCR debug] 已保存原始调试图片（解码异常）: {out_path}")
    except Exception as exc:
        print(f"[OCR debug] 保存调试图片失败（不影响识别结果）: {exc}")


def _cleanup_ocr_debug_images() -> None:
    """清理超过 {_OCR_DEBUG_RETENTION_DAYS} 天的 OCR 调试图片。"""
    try:
        if not _OCR_DEBUG_DIR.exists():
            return
        cutoff = time.time() - _OCR_DEBUG_RETENTION_DAYS * 86400
        removed = 0
        for f in _OCR_DEBUG_DIR.glob("*.png"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        if removed:
            print(f"[OCR debug] 已清理 {removed} 张超过 {_OCR_DEBUG_RETENTION_DAYS} 天的调试图片")
    except Exception as exc:
        print(f"[OCR debug] 清理调试图片失败: {exc}")


async def _periodic_ocr_debug_cleanup() -> None:
    """后台定时清理 OCR 调试图片。"""
    loop = asyncio.get_running_loop()
    interval = _OCR_DEBUG_CLEANUP_INTERVAL_SECONDS
    print(
        f"[OCR debug] 定时清理任务已启动: interval={interval}s, retention={_OCR_DEBUG_RETENTION_DAYS}d"
    )
    try:
        await loop.run_in_executor(None, _cleanup_ocr_debug_images)
        while True:
            await asyncio.sleep(interval)
            await loop.run_in_executor(None, _cleanup_ocr_debug_images)
    except asyncio.CancelledError:
        print("[OCR debug] 定时清理任务已停止")
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
        os.environ.get("OCR_REC_MODEL_DIR", "IQIDDET/models/OCR_rec_inference_best_accuracy")
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
    import gauge.region_ocr_api as _ocr_mod
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
    from gauge.region_ocr_api import RecognizeRequest as _BaseReq
    base_req = _BaseReq(image_base64=request.image_base64)
    return await _recognize_region(base_req)


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
        await loop.run_in_executor(executor, _sync_run_inference_via_script, request)
        
        inference_tasks[task_id]["status"] = "completed"
        inference_tasks[task_id]["progress"] = inference_tasks[task_id]["total"]
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Inference failed for task {task_id}: {error_msg}")
        inference_tasks[task_id]["status"] = "failed"
        inference_tasks[task_id]["error_message"] = str(e)


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
            "--ocr-rec-model-dir",    os.environ.get("OCR_REC_MODEL_DIR",    "IQIDDET/models/OCR_rec_inference_best_accuracy"),
            "--ocr-det-model-dir",    os.environ.get("OCR_DET_MODEL_DIR",    "IQIDDET/models/PP-OCRv5_server_det"),
            "--enable-ocr-orientation",
            "--ocr-orientation-model", os.environ.get("OCR_ORIENTATION_MODEL", "IQIDDET/models/ocr_orientation_model.pth"),
            "--ocr-orientation-device", iqi_device,
            "--ocr-device",           "gpu" if _cuda_available else "cpu",
            "--ocr-number-range",     "6,10-15",
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
    # 后台预热 OCR，不阻塞 health check
    app.state.ocr_warmup_task = asyncio.create_task(_warmup_ocr())
    app.state.ocr_debug_cleanup_task = asyncio.create_task(_periodic_ocr_debug_cleanup())


@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时释放后台任务和 OCR 资源。"""
    for task_name in ("ocr_warmup_task", "ocr_debug_cleanup_task"):
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
