# SpeakWise one-click build script
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  SpeakWise Build Script" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Building frontend..." -ForegroundColor Yellow
Set-Location frontend
npm run build
Set-Location $PSScriptRoot
Write-Host "[1/4] Frontend OK" -ForegroundColor Green

Write-Host "[2/4] Building Python backend (PyInstaller)..." -ForegroundColor Yellow
pyinstaller --onefile --name speakwise-backend `
  --add-data "backend/src/prompts;prompts" `
  --hidden-import=sse_starlette `
  --hidden-import=sqlmodel `
  --hidden-import=pypdf `
  --hidden-import=docx `
  --hidden-import=dotenv `
  --collect-all openai `
  backend/src/main.py
Write-Host "[2/4] Backend OK" -ForegroundColor Green

Write-Host "[3/4] Copying backend to dist..." -ForegroundColor Yellow
$backendDir = "dist/speakwise-backend"
New-Item -ItemType Directory -Force -Path $backendDir | Out-Null
Copy-Item "dist/speakwise-backend.exe" "$backendDir/" -Force
Write-Host "[3/4] Copy OK" -ForegroundColor Green

Write-Host "[4/4] Electron-builder packaging..." -ForegroundColor Yellow
Set-Location electron
npm run build
Set-Location $PSScriptRoot
Write-Host "[4/4] Electron OK" -ForegroundColor Green

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Get-ChildItem dist/*.exe 2>$null
Get-ChildItem dist/*.zip 2>$null
