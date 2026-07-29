#!/bin/bash
# ============================================================================
# HiRo FINAL PRODUCTION STARTUP (Host Machine Script)
# Manages the entire multi-container Docker stack.
# ============================================================================
set -e

echo "========================================"
echo "   HiRo System Startup Sequence"
echo "========================================"

# 1. Environment Check
if [ ! -f .env ]; then
    echo "❌ Error: .env file missing in root directory!"
    exit 1
fi

# 2. Shutdown, Cleanup, and Volume Reset (Preserve Ollama)
echo "🧹 Cleaning up old containers and volumes (excluding Ollama storage)..."

# Explicitly stop all services
docker compose down

# Use 'docker volume ls' to find project-specific volumes and exclude 'ollama_storage'
# Get the project name used by Docker Compose (usually the directory name)
PROJECT_PREFIX=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')
OLLAMA_VOLUME="${PROJECT_PREFIX}_ollama_storage"

# List and remove volumes matching the project prefix, excluding the Ollama volume
docker volume ls -q -f name="${PROJECT_PREFIX}_" | grep -v "$OLLAMA_VOLUME" | xargs -r docker volume rm

echo "✅ Cleared Mongo, Dgraph, and old container data."
echo "ℹ️ Ollama volume ($OLLAMA_VOLUME) preserved as requested."

# 3. Build & Start (Full rebuild to ensure clean configuration)
echo "🐳 Building & Starting Containers (Forcing rebuild)..."
docker compose up -d --build --force-recreate

# 4. Wait for Gateway Health (Wait for the exposed proxy on host port 80)
echo "⏳ Waiting for Nginx Gateway availability on host port 80..."
MAX_RETRIES=45
COUNT=0
URL="http://localhost:80"

until curl -s $URL > /dev/null; do
    echo "   ...waiting for gateway ($COUNT/$MAX_RETRIES)"
    sleep 2
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Timeout waiting for Nginx Gateway service."
        echo "   Checking logs for errors..."
        docker compose logs nginx_proxy | tail -n 20
        exit 1
    fi
done
echo "✅ Gateway is ONLINE."

# 5. Final Status
echo "========================================"
echo "   SYSTEM ONLINE"
echo "========================================"
echo "   Access Application: http://localhost"
echo "   Backend Docs:       http://localhost:8001/docs (Direct container access)"
echo "   Ollama:             http://localhost:11434"
echo "========================================"