#!/usr/bin/env bash

set -euo pipefail

# frontend/dev_start.sh
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-3000}"
NODE_ENV="${NODE_ENV:-development}"

echo "=== HiRo Frontend DEV Mode Startup ==="
echo "[INFO] Container running in development mode for hot-reloading."
echo "[INFO] NODE_ENV: $NODE_ENV"
echo "[INFO] PORT: $PORT"

# Environment validation for development
echo "[INFO] Validating environment variables..."

# Set defaults for development if not set
export REACT_APP_BACKEND_URL="${REACT_APP_BACKEND_URL:-http://localhost:8001}"
export REACT_APP_OLLAMA_URL="${REACT_APP_OLLAMA_URL:-http://localhost:11434}"
export REACT_APP_ENABLE_VISUAL_EDITS="${REACT_APP_ENABLE_VISUAL_EDITS:-true}"

# Log environment setup
echo "[INFO] REACT_APP_BACKEND_URL: $REACT_APP_B