@echo off
setlocal
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%dist\label_rec_no_box.exe"

if not exist "%EXE_PATH%" (
  echo [ERROR] Executable not found: %EXE_PATH%
  echo [ERROR] Run build_label_rec_no_box_windows.bat first.
  exit /b 1
)

start "" "%EXE_PATH%"
echo [OK] 标注器已启动。
echo [OK] 程序会弹出目录选择框，请选择待标注图片目录。
exit /b 0
