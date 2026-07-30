# HiRo local run (no Docker). Starts Postgres (self-managed cluster on 5433),
# MongoDB (local dbpath on 27017), then the FastAPI backend via uvicorn --reload.
# Frontend runs separately: cd frontend; npm start  (proxy -> :8001)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$pgBin = "C:\Program Files\PostgreSQL\15\bin"
$pgData = Join-Path $root ".localdb\pg"
$mongoData = Join-Path $root ".localdb\mongo"
$mongoLog = Join-Path $root ".localdb\mongo.log"

# --- Postgres ---
if (-not (Test-Path (Join-Path $pgData "PG_VERSION"))) {
  throw "Postgres cluster missing at $pgData. Re-run the one-time initdb setup."
}
& "$pgBin\pg_ctl.exe" -D $pgData status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Starting Postgres on 5433..."
  & "$pgBin\pg_ctl.exe" -D $pgData -l (Join-Path $root ".localdb\pg.log") -w start
} else { Write-Host "Postgres already running." }

# --- MongoDB ---
$mongod = Get-ChildItem "C:\Program Files\MongoDB\Server\*\bin\mongod.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $mongod) { throw "mongod.exe not found. Install MongoDB Server first." }
New-Item -ItemType Directory -Force -Path $mongoData | Out-Null
$mongoUp = Test-NetConnection -ComputerName localhost -Port 27017 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $mongoUp) {
  Write-Host "Starting MongoDB on 27017..."
  Start-Process -FilePath $mongod -ArgumentList @("--dbpath", $mongoData, "--port", "27017", "--logpath", $mongoLog, "--logappend") -WindowStyle Hidden
  Start-Sleep -Seconds 3
} else { Write-Host "MongoDB already running." }

# --- Backend env ---
Get-Content (Join-Path $root "backend\.env.local") | ForEach-Object {
  if ($_ -match '^\s*([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") }
}
$env:PYTHONUTF8 = "1"

Write-Host "Starting backend (uvicorn) on :8100..."
Set-Location (Join-Path $root "backend")
python -m uvicorn server:app --host 0.0.0.0 --port 8100
