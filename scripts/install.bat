@echo off
REM Install dependencies

cd /d "%~dp0.."

echo ============================================
echo Installing dependencies
echo ============================================
echo.

REM Stop any running uv processes
taskkill /F /IM uv.exe 2>nul

REM Clear uv cache
echo Clearing uv cache...
uv cache clean 2>nul

REM Remove incomplete virtual environment
if exist ".venv" (
    if not exist ".venv\Scripts\pip.exe" (
        echo Removing incomplete virtual environment...
        rmdir /s /q .venv
    )
)

REM Create virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        echo Please check if Python is installed: python --version
        pause
        exit /b 1
    )
)

REM Install using pip directly (bypass uv cache)
echo Installing dependencies with pip...
.venv\Scripts\pip.exe install playwright httpx pyyaml loguru

echo.
echo ============================================
echo Installation complete
echo ============================================
echo.

pause
