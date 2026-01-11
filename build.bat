@echo off
REM Build script for SC Signature Scanner
REM Creates a standalone .exe distribution

echo ========================================
echo  SC Signature Scanner - Build Script
echo ========================================
echo.

REM Check if running from correct directory
if not exist "main.py" (
    echo ERROR: Run this script from the SC_Signature_Scanner directory
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Check/install PyInstaller
echo Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Run PyInstaller
echo.
echo Building executable...
echo.
pyinstaller SC_Signature_Scanner.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ========================================
    echo  BUILD FAILED
    echo ========================================
    pause
    exit /b 1
)

REM Copy additional files to dist folder
echo.
echo Copying additional files...
if not exist "dist\SC_Signature_Scanner\data" mkdir "dist\SC_Signature_Scanner\data"
copy "data\combat_analyst_db.json" "dist\SC_Signature_Scanner\data\" >nul

REM Create empty config so the app knows where to save
echo {} > "dist\SC_Signature_Scanner\config.json"

echo.
echo ========================================
echo  BUILD COMPLETE
echo ========================================
echo.
echo Output: dist\SC_Signature_Scanner\
echo Executable: dist\SC_Signature_Scanner\SC_Signature_Scanner.exe
echo.
echo You can distribute the entire SC_Signature_Scanner folder.
echo.

REM Open the dist folder
explorer "dist\SC_Signature_Scanner"

pause
