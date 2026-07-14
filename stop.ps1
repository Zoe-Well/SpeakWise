# SpeakWise stop script
Write-Host "Stopping SpeakWise..." -ForegroundColor Yellow

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "Done" -ForegroundColor Green
