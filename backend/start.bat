@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo [ReviewMind] Starting backend...

:: 禁用 Python 输出缓冲，让日志即时显示
set PYTHONUNBUFFERED=1

if exist ".venv\Scripts\python.exe" (
    echo [ReviewMind] Using venv Python
    .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
) else (
    echo [ReviewMind] venv not found, using system Python
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info
)

pause