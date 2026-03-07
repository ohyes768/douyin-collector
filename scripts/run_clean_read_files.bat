@echo off
REM 已读文件清理程序启动脚本

cd /d "%~dp0.."

echo ============================================
echo 已读文件清理程序启动
echo ============================================
echo.

REM Check virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found
    echo Please run: scripts\install.bat
    pause
    exit /b 1
)

REM Run clean read files program
.venv\Scripts\python.exe clean_read_files.py

pause