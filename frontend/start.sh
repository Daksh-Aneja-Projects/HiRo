# /start.sh (Host Machine Script)

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
# Shutdown containers first
docker compose down

# CRITICAL FIX: Simplified and robust volume removal logic
PROJECT_PREFIX=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')
OLLAMA_VOLUME="${PROJECT_PREFIX}_ollama_storage"

# Get all volumes related to the project
ALL_VOLUMES=$(docker volume ls -q -f name="${PROJECT_PREFIX}_")

# Filter out the Ollama volume and remove the rest
VOLUMES_TO_REMOVE=""
for vol in $ALL_VOLUMES; do
    if [[ "$vol" != "$OLLAMA_VOLUME" ]]; then
        VOLUMES_TO_REMOVE="$VOLUMES_TO_REMOVE $vol"
    fi
done

if [ -n "$VOLUMES_TO_REMOVE" ]; then
    docker volume rm $VOLUMES_TO_REMOVE
    echo "✅ Cleared Mongo, Dgraph, and old container data."
else
    echo "ℹ️ No volumes found to clear (or only Ollama volume exists)."
fi

echo "ℹ️ Ollama volume ($OLLAMA_VOLUME) preserved as requested."

# 3. Build & Start (Using smart build cache, forcing recreation only on changes)
echo "🐳 Building & Starting Containers (Relying on smart build cache)..."
# CRITICAL FIX: Ensure the compose is run cleanly after volume cleanup
docker compose up -d 

# 4. Wait for Gateway Health (Wait for the exposed proxy on host port 80)
echo "⏳ Waiting for Nginx Gateway availability on host port 80..."
MAX_RETRIES=45
COUNT=0
URL="http://localhost:80/health" # CRITICAL FIX: Use the specific /health endpoint
until curl -s $URL | grep -q "healthy"; do
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
echo "========================================"