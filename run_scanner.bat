@echo off
REM SC Signature Scanner Launcher
REM ==============================

cd /d "%~dp0"

echo SC Signature Scanner
echo ====================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.10+ and add to PATH
    pause
    exit /b 1
)

REM Check Tesseract
where tesseract >nul 2>&1
if errorlevel 1 (
    echo WARNING: Tesseract OCR not found in PATH
    echo OCR functionality may not work
    echo Install from: https://github.com/UB-Mannheim/tesseract/wiki
    echo.
)

REM Launch
python main.py

pause
