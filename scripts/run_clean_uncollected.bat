@echo off
REM 取消收藏清理程序启动脚本

cd /d "%~dp0.."

echo ============================================
echo 取消收藏清理程序启动
echo ============================================
echo.

REM Check virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found
    echo Please run: scripts\install.bat
    pause
    exit /b 1
)

REM Run clean uncollected program
.venv\Scripts\python.exe clean_uncollected.py

pause