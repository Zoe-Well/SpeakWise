@echo off
chcp 65001 >nul
title 停止 SpeakWise

echo 正在停止 SpeakWise 服务...

:: 杀掉后端 Python 进程（uvicorn）
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list ^| findstr "PID"') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 杀掉前端 Vite/Node 进程
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq node.exe" /fo list ^| findstr "PID"') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo ✓ 已停止所有 SpeakWise 服务。
timeout /t 2 >nul
