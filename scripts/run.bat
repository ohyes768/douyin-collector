@echo off
REM douyin-collector startup script

cd /d "%~dp0.."

echo ============================================
echo douyin-collector starting
echo ============================================
echo.

REM Check virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found
    echo Please run: scripts\install.bat
    pause
    exit /b 1
)

REM Run main program
.venv\Scripts\python.exe main.py

pause
