#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIVision 绿色独立便携版 (Portable Standalone) 打包脚本
将当前完整 GPU 依赖环境 (py11) 与模型、代码整合为一个自包含目录。
任意换电脑 (只要有 NVIDIA 显卡与驱动) 均可即拷即用，无需配置 Python / Conda。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def run_cmd(cmd, check=True):
    print(f">> 执行: {cmd}")
    res = subprocess.run(cmd, shell=True)
    if check and res.returncode != 0 and res.returncode < 8:  # robocopy < 8 为成功
        print(f"警告/错误: 退出码 {res.returncode}")
    return res.returncode

def main():
    root_dir = Path(r"I:\项目\AIVision").resolve()
    weld_dir = root_dir / "model" / "weld"
    conda_env_dir = Path(r"C:\Users\lucas\.conda\envs\py11").resolve()
    
    # 默认输出目录
    target_dir = root_dir / "AIVision_Portable"
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1]).resolve()

    print("=" * 60)
    print(" 开始构建 AIVision 绿色便携独立运行包")
    print(f" 源环境: {conda_env_dir}")
    print(f" 目标目录: {target_dir}")
    print("=" * 60)

    target_dir.mkdir(parents=True, exist_ok=True)
    runtime_target = target_dir / "runtime"
    model_target = target_dir / "model" / "weld"

    # 1. 复制 runtime 环境 (使用 robocopy 快速多线程复制，排除 pycache 与临时缓存)
    print("\n[1/5] 同步运行环境 (Python 3.11 + CUDA + PyTorch + Paddle)...")
    robocopy_runtime = (
        f'robocopy "{conda_env_dir}" "{runtime_target}" /E /MT:8 '
        f'/XD "__pycache__" ".pytest_cache" "pip-cache" /XF "*.pyc" "*.pdb"'
    )
    run_cmd(robocopy_runtime, check=False)

    # 2. 复制核心程序与模型权重
    print("\n[2/5] 同步核心程序与模型权重...")
    robocopy_weld = (
        f'robocopy "{weld_dir}" "{model_target}" /E /MT:8 '
        f'/XD "__pycache__" "verify_out" ".git" "out" /XF "*.pyc" "*.tmp"'
    )
    run_cmd(robocopy_weld, check=False)

    # 3. 复制主可执行启动器 AIVision.exe
    print("\n[3/5] 安装独立无黑框主启动器 AIVision.exe...")
    launcher_src = weld_dir / "launcher" / "AIVision_Launcher.exe"
    launcher_dst = target_dir / "AIVision.exe"
    shutil.copy2(launcher_src, launcher_dst)

    # 4. 生成备用控制台排错启动脚本
    print("\n[4/5] 生成备用控制台启动脚本...")
    bat_content = """@echo off
rem AIVision 绿色独立便携版 - 控制台启动脚本 (用于查看运行日志或排错)
chcp 65001 >nul
cd /d "%~dp0model\\weld"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set PYTHONPATH=%~dp0model\\weld\\IQIDDET\\src;%~dp0model\\weld\\IQIDDET;%~dp0model\\weld
set PATH=%~dp0runtime;%~dp0runtime\\Scripts;%~dp0runtime\\Library\\bin;%~dp0runtime\\Lib\\site-packages\\torch\\lib;%PATH%
"%~dp0runtime\\python.exe" -m desktop.app %*
if errorlevel 1 (
    echo.
    echo ========================================
    echo 程序运行结束或发生异常 (错误代码: %errorlevel%)
    echo ========================================
    pause
)
"""
    bat_file = target_dir / "启动AIVision(控制台排错).bat"
    with open(bat_file, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # 5. 生成说明文档
    print("\n[5/5] 生成使用说明文档...")
    readme_content = """===============================================================
       AIVision 智能焊缝缺陷检测系统 - 绿色独立便携版 (Portable)
===============================================================

【系统简介】
本软件包已内置完整的独立运行环境与深度学习算法底层依赖：
- Python 3.11 独立运行时
- PyTorch 2.5 + CUDA 12.1 + cuDNN (支持 RTX 30/40 等主流 GPU)
- PaddlePaddle-GPU 3.3
- PyQt6 工业级桌面操作界面
- 完整模型权重 (0208primary.pth、weldROI4.pt、OCR 模型等)

【换机运行要求】
1. 操作系统：Windows 10 / Windows 11 (64位)
2. 硬件要求：配备 NVIDIA 独立显卡，显卡驱动推荐版本 >= 525 (支持 CUDA 12)
3. 绿色免安装：无需目标电脑安装 Python，无需安装 Anaconda，随拷即用！

【使用方法】
- 正常运行：直接双击根目录下的 "AIVision.exe" 即可启动图形界面 (无黑框、秒开)。
- 排错运行：若在某些特殊电脑上运行闪退，可双击 "启动AIVision(控制台排错).bat" 查看完整报错日志。

【关于分发】
您可以直接将整个 "AIVision_Portable" 文件夹拷贝到 U 盘、移动硬盘或通过局域网传输到目标电脑的任意目录运行。
===============================================================
"""
    readme_file = target_dir / "使用说明.txt"
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("\n" + "=" * 60)
    print(f" 便携独立包构建完成！输出目录：\n {target_dir}")
    print("=" * 60)

if __name__ == "__main__":
    main()

