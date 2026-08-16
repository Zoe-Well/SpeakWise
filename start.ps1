# SpeakWise one-click launcher (PowerShell)
$ErrorActionPreference = "Continue"
$ROOT = $PSScriptRoot
Set-Location $ROOT

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  SpeakWise - Interview Copilot" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check environment
Write-Host "[1/4] Checking environment..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Python 3.12+ not found" -ForegroundColor Red; pause; exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: Node.js 20+ not found" -ForegroundColor Red; pause; exit 1
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing uv..." -ForegroundColor Gray
    irm https://astral.sh/uv/install.ps1 | iex
}
$pythonVer = (python --version 2>&1)
$nodeVer   = (node --version 2>&1)
Write-Host "  Python: $pythonVer  |  Node: $nodeVer" -ForegroundColor Gray

# 2. Backend deps
Write-Host "[2/4] Backend dependencies..." -ForegroundColor Yellow
uv sync 2>&1 | Out-Null
Write-Host "[2/4] Backend ready" -ForegroundColor Green

# 3. Frontend deps
Write-Host "[3/4] Frontend dependencies..." -ForegroundColor Yellow
Set-Location "$ROOT\frontend"
if (-not (Test-Path "node_modules")) {
    Write-Host "  Installing..." -ForegroundColor Gray
    npm install 2>&1 | Out-Null
}
Set-Location $ROOT
Write-Host "[3/4] Frontend ready" -ForegroundColor Green

# 4. Start services
Write-Host "[4/4] Starting services..." -ForegroundColor Yellow

# Use the same backend port as Vite and Electron.
$BACKEND_PORT = 8001
$conn = Get-NetTCPConnection -LocalPort $BACKEND_PORT -ErrorAction SilentlyContinue
if ($conn) {
    Write-Host "  Port $BACKEND_PORT is in use (PID $($conn.OwningProcess))" -ForegroundColor Gray
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "  Killing $($proc.ProcessName) (PID $($conn.OwningProcess))..." -ForegroundColor Gray
        Stop-Process -Id $conn.OwningProcess -Force
        Start-Sleep 1
    } else {
        Write-Host "  WARNING: Zombie socket detected (PID $($conn.OwningProcess) not found)" -ForegroundColor Yellow
        Write-Host "  ERROR: Port $BACKEND_PORT cannot be released." -ForegroundColor Red
        exit 1
    }
}

Start-Process -FilePath "uv" -ArgumentList "run","uvicorn","backend.src.main:app","--host","127.0.0.1","--port","8001" -WorkingDirectory $ROOT -WindowStyle Minimized

# Wait for backend
Write-Host "  Waiting for backend..." -ForegroundColor Gray
do {
    Start-Sleep -Seconds 1
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BACKEND_PORT/api/health" -TimeoutSec 2 -ErrorAction SilentlyContinue } catch {}
} while (-not $health -or $health.status -ne "ok")
Write-Host "  Backend:  http://127.0.0.1:$BACKEND_PORT" -ForegroundColor Green

# Start frontend in a new window
Start-Process -FilePath "npx.cmd" -ArgumentList "vite","--host" -WorkingDirectory "$ROOT\frontend" -WindowStyle Minimized

# Wait for frontend
Write-Host "  Waiting for frontend..." -ForegroundColor Gray
do {
    Start-Sleep -Seconds 1
    try { $resp = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 2 -ErrorAction SilentlyContinue } catch {}
} while (-not $resp -or $resp.StatusCode -ne 200)
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green

# Open browser
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  All services running!" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://127.0.0.1:$BACKEND_PORT"
Write-Host "  API Docs: http://127.0.0.1:$BACKEND_PORT/docs"
Write-Host ""
Write-Host "  Run .\stop.ps1 to stop all services"
Write-Host "======================================" -ForegroundColor Cyan
