@echo off
chcp 65001 >nul
echo ========================================================
echo   EduGrade AI - 教学作业上传与自动评分系统 (Windows 启动)
echo ========================================================

set ROOT_DIR=%~dp0

if not exist "%ROOT_DIR%backend\.env" (
    copy "%ROOT_DIR%backend\.env.example" "%ROOT_DIR%backend\.env"
    echo [提示] 已生成默认 backend\.env 配置文件，请按需配置 GEMINI_API_KEY
)

echo [1/2] 正在后台启动 FastAPI 后端服务 (http://127.0.0.1:8000)...
cd /d "%ROOT_DIR%backend"
if not exist ".venv" (
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
start "EduGrade-Backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] 正在启动 Vue 3 + Vite 前端服务 (http://127.0.0.1:5173)...
cd /d "%ROOT_DIR%frontend"
if not exist "node_modules" (
    call npm install
)
call npm run dev
