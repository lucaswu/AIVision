@echo off
rem AIVision 桌面版启动脚本。
rem 用法：双击运行；或在命令行指定 Python 解释器：run_desktop.bat D:\envs\aivision\python.exe
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONPATH=%~dp0IQIDDET\src;%~dp0IQIDDET;%~dp0
set PYTHON_BIN=%~1
if "%PYTHON_BIN%"=="" set PYTHON_BIN=python
"%PYTHON_BIN%" -m desktop.app
if errorlevel 1 pause
