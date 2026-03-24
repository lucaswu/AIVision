@echo off
setlocal
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv_win_build"
set "DIST_EXE=%SCRIPT_DIR%dist\label_rec_no_box.exe"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher "py" was not found. Install Python 3.10+ first.
  exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [INFO] Creating build virtualenv...
  py -3 -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 exit /b 1

echo [INFO] Installing build dependencies...
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r "%SCRIPT_DIR%requirements_labeler_windows.txt"
if errorlevel 1 exit /b 1

pushd "%SCRIPT_DIR%"
echo [INFO] Building Windows executable...
pyinstaller --noconfirm --clean --onefile --name label_rec_no_box --collect-all PIL --hidden-import tkinter --hidden-import tkinter.filedialog --hidden-import tkinter.messagebox "%SCRIPT_DIR%label_rec_no_box.py"
set "BUILD_STATUS=%ERRORLEVEL%"
popd

if not "%BUILD_STATUS%"=="0" (
  echo [ERROR] PyInstaller build failed.
  exit /b %BUILD_STATUS%
)

if not exist "%DIST_EXE%" (
  echo [ERROR] Build finished but executable was not found: %DIST_EXE%
  exit /b 1
)

echo [OK] Build complete: %DIST_EXE%
echo [OK] You can now double-click label_rec_no_box.exe
exit /b 0
