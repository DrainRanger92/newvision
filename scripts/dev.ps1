# Curtain Reader — Local Dev Runner (PowerShell)
# Starts backend (uvicorn) and frontend (vite) concurrently.

$ErrorActionPreference = "Stop"

Write-Host "[Dev] Starting backend on :8000..." -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000" -NoNewWindow -PassThru | Out-Null

Start-Sleep -Seconds 2

Write-Host "[Dev] Starting frontend on :5173..." -ForegroundColor Cyan
Push-Location frontend
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -NoNewWindow -PassThru | Out-Null
Pop-Location

Write-Host "[Dev] Both services running." -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Yellow
Write-Host "  Health:   http://localhost:8000/health" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop (manually close terminal windows)." -ForegroundColor Gray
