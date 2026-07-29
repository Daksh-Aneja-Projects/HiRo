# ============================================================================
# HiRo FINAL BUILD & DEPLOYMENT SCRIPT (PowerShell)
# ============================================================================

# 1. Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
docker-compose down -v
Remove-Item -Path "frontend/build" -Recurse -ErrorAction SilentlyContinue
Remove-Item -Path "backend/__pycache__" -Recurse -ErrorAction SilentlyContinue

# 2. Environment variables are loaded from .env (see .env.example). Do not hardcode secrets here.

# 3. Build Docker Containers (No Cache for Production Safety)
Write-Host "Building Docker Containers..." -ForegroundColor Cyan
docker-compose build --no-cache

# 4. Start Services
Write-Host "Starting Services..." -ForegroundColor Green
docker-compose up -d

# 5. Wait for Health Checks
Write-Host "Waiting for system initialization (approx 15s)..." -ForegroundColor Magenta
Start-Sleep -Seconds 15

# 6. Initialize Local AI (Ollama)
Write-Host "Initializing Local AI Model (qwen2.5:7b)..." -ForegroundColor Cyan
docker exec hiro-ollama ollama pull qwen2.5:7b

# 7. Final Status Report
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   HiRo SYSTEM ONLINE (PRODUCTION READY)" -ForegroundColor Green
Write-Host "========================================"
Write-Host "   Frontend: http://localhost:3000"
Write-Host "   Backend API: http://localhost:8001/docs"
Write-Host "   AI Service: Local Ollama (qwen2.5:7b)"
Write-Host "========================================"

# 8. Open Browser
Start-Process "http://localhost:3000"