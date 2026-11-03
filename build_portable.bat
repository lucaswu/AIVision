@echo off
rem ===============================================================
rem 一键打包构建 AIVision 绿色独立便携发行版 (AIVision_Portable)
rem 内置完整运行依赖 (Python 3.11 + PyTorch CUDA 12.1 + Paddle + PyQt6 + 模型权重)
rem ===============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo ===============================================================
echo 正在准备打包 AIVision 绿色独立便携版...
echo 输出目录: %~dp0AIVision_Portable
echo ===============================================================

set PYTHON_EXE=C:\Users\lucas\.conda\envs\py11\python.exe
if not exist "%PYTHON_EXE%" (
    echo [错误] 未找到指定的 Conda Python 环境: %PYTHON_EXE%
    echo 请确认 py11 环境路径是否正确。
    pause
    exit /b 1
)

"%PYTHON_EXE%" "model\weld\launcher\build_portable.py" %*

echo.
echo 打包执行完成。
pause
