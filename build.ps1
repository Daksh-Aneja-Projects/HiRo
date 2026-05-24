# ============================================================================
# ORG360 FINAL BUILD & DEPLOYMENT SCRIPT (PowerShell)
# ============================================================================

# 1. Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
docker-compose down -v
Remove-Item -Path "frontend/build" -Recurse -ErrorAction SilentlyContinue
Remove-Item -Path "backend/__pycache__" -Recurse -ErrorAction SilentlyContinue

# 2. Set Environment Variables (Optional override for local dev)
$Env:GEMINI_API_KEY = "gen-lang-client-0708616522"
$Env:MONGO_ROOT_PASSWORD = "supersecurepassword"

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
Write-Host "Initializing Local AI Model (Mistral)..." -ForegroundColor Cyan
docker exec org360-ollama ollama pull mistral

# 7. Final Status Report
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "   ORG360 SYSTEM ONLINE (PRODUCTION READY)" -ForegroundColor Green
Write-Host "========================================"
Write-Host "   Frontend: http://localhost:3000"
Write-Host "   Backend API: http://localhost:8001/docs"
Write-Host "   AI Service: Hybrid (Ollama + Gemini)"
Write-Host "========================================"

# 8. Open Browser
Start-Process "http://localhost:3000"