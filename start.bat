@echo off
chcp 65001 >nul
title SpeakWise 智能面试助手

echo ======================================
echo   SpeakWise 智能面试助手 — 一键启动
echo ======================================
echo.

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.12+
    pause
    exit /b 1
)

:: 检查 Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Node.js，请先安装 Node.js 20+
    pause
    exit /b 1
)

:: 检查 uv（Python 包管理器）
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 正在安装 uv...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
)

:: 后端依赖
echo [1/4] 检查后端依赖...
cd /d "%~dp0"
uv sync --quiet 2>nul
if %errorlevel% neq 0 (
    echo [INFO] 正在安装后端依赖...
    uv sync
)
echo [1/4] 后端依赖就绪 ✓

:: 前端依赖
echo [2/4] 检查前端依赖...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [INFO] 正在安装前端依赖...
    call npm install
)
echo [2/4] 前端依赖就绪 ✓

:: 启动后端
echo [3/4] 启动后端服务 (127.0.0.1:8001)...
cd /d "%~dp0"
start "SpeakWise Backend" cmd /c "uv run uvicorn backend.src.main:app --host 127.0.0.1 --port 8001"

:: 等后端就绪
echo       等待后端就绪...
:wait_backend
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:8001/api/health >nul 2>&1
if %errorlevel% neq 0 goto wait_backend
echo [3/4] 后端就绪 ✓ (http://127.0.0.1:8001)

:: 启动前端
echo [4/4] 启动前端 (http://localhost:5173)...
cd /d "%~dp0frontend"
start "SpeakWise Frontend" cmd /c "npx vite --host"

:: 等待前端就绪
:wait_frontend
timeout /t 2 /nobreak >nul
curl -s http://localhost:5173 >nul 2>&1
if %errorlevel% neq 0 goto wait_frontend

:: 打开浏览器
start "" "http://localhost:5173"

echo.
echo ======================================
echo   ✓ 启动成功！
echo.
echo   前端: http://localhost:5173
echo   后端: http://127.0.0.1:8001
echo   API文档: http://127.0.0.1:8001/docs
echo.
echo   关闭此窗口不会停止服务。
echo   运行 stop.bat 停止所有服务。
echo ======================================

pause
