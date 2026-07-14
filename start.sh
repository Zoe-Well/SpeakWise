#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "正在停止服务..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  echo "✓ 已停止"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "======================================"
echo "  SpeakWise 智能面试助手 — 一键启动"
echo "======================================"
echo ""

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] 未找到 python3"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[ERROR] 未找到 node"; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "[INFO] 安装 uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }

# 后端依赖
echo "[1/4] 检查后端依赖..."
cd "$ROOT_DIR"
uv sync --quiet 2>/dev/null || uv sync
echo "[1/4] 后端依赖就绪 ✓"

# 前端依赖
echo "[2/4] 检查前端依赖..."
cd "$ROOT_DIR/frontend"
[ -d "node_modules" ] || npm install
echo "[2/4] 前端依赖就绪 ✓"

# 启动后端
echo "[3/4] 启动后端 (127.0.0.1:8000)..."
cd "$ROOT_DIR"
uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 等待后端就绪
echo "     等待后端就绪..."
until curl -s http://127.0.0.1:8000/api/health >/dev/null 2>&1; do sleep 1; done
echo "[3/4] 后端就绪 ✓ (http://127.0.0.1:8000)"

# 启动前端
echo "[4/4] 启动前端 (http://localhost:5173)..."
cd "$ROOT_DIR/frontend"
npx vite --host &
FRONTEND_PID=$!

# 等待前端就绪
until curl -s http://localhost:5173 >/dev/null 2>&1; do sleep 1; done
echo "[4/4] 前端就绪 ✓"

echo ""
echo "======================================"
echo "  ✓ 启动成功！"
echo ""
echo "  前端:    http://localhost:5173"
echo "  后端:    http://127.0.0.1:8000"
echo "  API文档: http://127.0.0.1:8000/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "======================================"

# 保持前台运行
wait
