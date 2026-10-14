#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  EduGrade AI - 教学作业上传与自动评分系统 一键启动脚本"
echo "========================================================"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. 检查并初始化后端 .env
if [ ! -f "$ROOT_DIR/backend/.env" ]; then
  cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
  echo "[提示] 已从 .env.example 生成默认 backend/.env，可在其中填入 GEMINI_API_KEY"
fi

# 2. 启动后端 FastAPI 服务
echo "[1/2] 正在启动后端 FastAPI 服务 (http://127.0.0.1:8000)..."
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 3. 启动前端 Vue 3 + Vite 服务
echo "[2/2] 正在启动前端 Vue 3 + Vite 服务 (http://127.0.0.1:5173)..."
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  npm install
fi

trap "kill $BACKEND_PID 2>/dev/null || true" EXIT
npm run dev
