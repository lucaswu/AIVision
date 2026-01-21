#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIVision OCR 推理服务 API 入口
提供 HTTP 接口调用 OCR 模型

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

# 检查 PaddlePaddle 是否可用
_paddle_available = False
_cuda_available = False

try:
    import paddle
    _paddle_available = True
    _cuda_available = paddle.device.is_compiled_with_cuda()
except ImportError:
    pass

# ==============================================================================
# FastAPI 应用配置
# ==============================================================================

app = FastAPI(
    title="AIVision OCR Service",
    description="焊缝X光底片 OCR 识别服务",
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
    max_size: int = Field(default=1920, description="图片最大尺寸")
    save_annotations: bool = Field(default=True, description="是否保存标注图片")


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
    paddle_available: bool
    cuda_available: bool


# ==============================================================================
# API 端点
# ==============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        paddle_available=_paddle_available,
        cuda_available=_cuda_available
    )


@app.get("/")
async def root():
    """根路径"""
    return {"service": "AIVision OCR Service", "version": "1.0.0"}


@app.post("/inference/submit", response_model=InferenceResponse)
async def submit_inference(request: InferenceRequest, background_tasks: BackgroundTasks):
    """
    提交 OCR 推理任务
    
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
    
    # 在后台执行推理
    background_tasks.add_task(run_inference_task, request)
    
    return InferenceResponse(
        task_id=task_id,
        status="accepted",
        message=f"OCR task submitted with {len(request.file_paths)} files"
    )


@app.get("/inference/{task_id}/status", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询 OCR 任务状态"""
    if task_id not in inference_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = inference_tasks[task_id]
    
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
    """获取 OCR 结果"""
    if task_id not in inference_tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task = inference_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Task is not completed. Current status: {task['status']}"
        )
    
    # 读取结果文件
    result_path = Path(f"/app/data/results/{task_id}/ocr_results.json")
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
# 推理执行逻辑 - 调用 OCR_main.py 脚本
# ==============================================================================

async def run_inference_task(request: InferenceRequest):
    """执行 OCR 任务"""
    task_id = request.task_id
    
    try:
        inference_tasks[task_id]["status"] = "processing"
        
        # 在线程池中执行同步推理代码
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, _sync_run_ocr_via_script, request)
        
        inference_tasks[task_id]["status"] = "completed"
        inference_tasks[task_id]["progress"] = inference_tasks[task_id]["total"]
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"OCR failed for task {task_id}: {error_msg}")
        inference_tasks[task_id]["status"] = "failed"
        inference_tasks[task_id]["error_message"] = str(e)


def _sync_run_ocr_via_script(request: InferenceRequest):
    """
    通过调用 OCR_main.py 脚本执行 OCR
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
    
    # 构建命令
    script_path = PROJECT_ROOT / "OCR_main.py"
    cmd = [
        sys.executable,  # python3
        str(script_path),
        "--file-list", str(file_list_path),
        "--output-dir", str(output_dir),
        "--results-json", "ocr_results.json",
        "--max-size", str(request.max_size),
    ]
    
    # 是否保存标注图片
    if not request.save_annotations:
        cmd.append("--no-annotation")
    
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
            raise RuntimeError(f"OCR script exited with code {process.returncode}")
        
        # 验证结果文件存在
        result_file = output_dir / "ocr_results.json"
        if not result_file.exists():
            raise RuntimeError("OCR completed but result file not found")
        
        print(f"[Task {task_id}] OCR completed successfully")
        
    except Exception as e:
        print(f"[Task {task_id}] Error: {e}")
        raise


# ==============================================================================
# 启动事件
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    """服务启动时的初始化"""
    print("=" * 60)
    print("AIVision OCR Service Starting...")
    print(f"PaddlePaddle available: {_paddle_available}")
    print(f"CUDA available: {_cuda_available}")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
