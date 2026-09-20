@echo off
setlocal
REM =====================================================================
REM  Stem-to-MIDI — Windows build script
REM  Run this on a Windows PC with Python 3.11 installed
REM  (tick "Add python.exe to PATH" during the Python install).
REM  Can be launched from anywhere (double-clicked, from cmd, even as
REM  admin): it always switches to the project root folder first.
REM =====================================================================

REM --- Always run from the project root (two levels above this file) ----
cd /d "%~dp0..\.."
if not exist packaging\windows\build.bat (
    echo ERROR: Could not find the project files. Make sure build.bat is
    echo inside the packaging\windows folder of the unzipped stem-to-midi folder.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found on PATH.
    echo Install Python 3.11 from https://www.python.org/downloads/ and tick "Add python to PATH".
    pause
    exit /b 1
)

echo --- Python version ---
python --version

REM --- 1. Virtual environment -------------------------------------------
if not exist venv-win (
    echo --- Creating virtual environment ---
    python -m venv venv-win
)
call venv-win\Scripts\activate.bat

python -m pip install --upgrade pip

REM --- 2. PyTorch CPU builds (NOT the multi-GB CUDA wheels on PyPI) -----
echo --- Installing torch CPU ---
pip install --timeout 120 --retries 10 ^
    torch==2.14.0+cpu torchaudio==2.11.0+cpu ^
    --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo TORCH INSTALL FAILED & pause & exit /b 1 )

REM --- 3. Everything else -------------------------------------------------
echo --- Installing requirements ---
pip install -r packaging\windows\requirements-windows.txt
if errorlevel 1 ( echo REQUIREMENTS INSTALL FAILED & pause & exit /b 1 )

REM --- 4. Demucs, then basic-pitch WITHOUT TensorFlow --------------------
echo --- Installing demucs ---
pip install demucs==4.1.0
if errorlevel 1 ( echo DEMUCS INSTALL FAILED & pause & exit /b 1 )

echo --- Installing basic-pitch without TensorFlow (ONNX model is used) ---
pip install --no-deps basic-pitch==0.4.0
if errorlevel 1 ( echo BASIC-PITCH INSTALL FAILED & pause & exit /b 1 )

REM --- 5. Headless smoke test ---------------------------------------------
echo --- Running smoke test ---
set QT_QPA_PLATFORM=offscreen
set BP_MODEL=onnx
python -m app.smoke_test
if errorlevel 1 ( echo SMOKE TEST FAILED & pause & exit /b 1 )

REM --- 6. Build the .exe ----------------------------------------------------
echo --- Building with PyInstaller ---
python -m PyInstaller packaging\windows\stem2midi.spec --noconfirm --clean
if errorlevel 1 ( echo PYINSTALLER BUILD FAILED & pause & exit /b 1 )

echo.
echo =====================================================================
echo  BUILD DONE: dist\Stem2MIDI\Stem2MIDI.exe
echo  To make an installer, open packaging\windows\installer.iss in
echo  Inno Setup and press Compile.
echo =====================================================================
pause
