# verify-fix.ps1
Write-Host "=========================================="
Write-Host "🔍 VERIFYING ORG360 FIXES (PowerShell)"
Write-Host "=========================================="

$ErrorActionPreference = "Stop"

# 1. Static Check
Write-Host "1. Checking for guarded uvicorn run in server.py..."
if (Select-String -Path "backend/server.py" -Pattern 'if __name__ == "__main__":' -Quiet) {
    Write-Host "✅ server.py has main guard." -ForegroundColor Green
} else {
    Write-Host "❌ server.py missing main guard!" -ForegroundColor Red
    exit 1
}

Write-Host "2. Checking Nginx Config existence..."
if (Test-Path "frontend/nginx.conf") {
    Write-Host "✅ nginx.conf exists." -ForegroundColor Green
} else {
    Write-Host "❌ frontend/nginx.conf missing!" -ForegroundColor Red
    exit 1
}

# 2. Docker Build & Run
Write-Host "3. Building and Starting Docker Stack..."
# We use cmd /c to ensure docker-compose runs correctly if it's a bat file on some Windows setups, though direct usually works.
docker-compose down -v
docker-compose build --pull --no-cache
docker-compose up -d

Write-Host "⏳ Waiting 15s for containers to stabilize..."
Start-Sleep -Seconds 15

# 3. Runtime Checks
Write-Host "4. Checking Backend Logs for Import Errors..."
$logs = docker-compose logs backend
if ($logs | Select-String "SpawnProcess-1" -Quiet) {
    Write-Host "❌ Spawn Error Detected in Backend Logs!" -ForegroundColor Red
    docker-compose logs backend --tail=20
    exit 1
} else {
    Write-Host "✅ No Import-Time Spawn Errors detected." -ForegroundColor Green
}

Write-Host "5. Checking Backend Health API..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Backend Health OK (200)" -ForegroundColor Green
    } else {
        Write-Host "❌ Backend Health Failed ($($response.StatusCode))" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Backend Health Failed to Connect: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "6. Checking Nginx API Proxy..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000/api/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ Nginx Proxy OK (200)" -ForegroundColor Green
    } else {
        Write-Host "❌ Nginx Proxy Failed ($($response.StatusCode))" -ForegroundColor Red
        Write-Host "   Expected 200 from http://localhost:3000/api/health"
        exit 1
    }
} catch {
    Write-Host "❌ Nginx Proxy Failed to Connect: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "7. Checking Favicon Silence..."
try {
    # 204 No Content is success for us here. -SkipHttpErrorCheck allows 404/etc without throwing exception immediately
    $response = Invoke-WebRequest -Uri "http://localhost:3000/favicon.ico" -UseBasicParsing -SkipHttpErrorCheck
    if ($response.StatusCode -eq 204) {
        Write-Host "✅ Favicon Silenced (204)" -ForegroundColor Green
    } else {
        Write-Host "❌ Favicon Config Failed ($($response.StatusCode))" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Favicon Check Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "=========================================="
Write-Host "🎉 ALL CHECKS PASSED - SYSTEM FIXED" -ForegroundColor Green
Write-Host "=========================================="