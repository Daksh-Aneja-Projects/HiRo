#!/bin/sh
# ./nginx-wait.sh - FINAL ROBUST VERSION
# Waits for backend service to be ready before starting NGINX

set -e

# CRITICAL FIX: Checking the deepest health endpoint (/api/health) to ensure router is mounted.
BACKEND_HOST="backend:8001"
HEALTH_CHECK_URL="http://${BACKEND_HOST}/api/health"
TIMEOUT=60
INTERVAL=2

echo "⏳ Waiting for backend service at ${HEALTH_CHECK_URL}..."

start_time=$(date +%s)

# Loop until curl succeeds (exit code 0)
# -f fails on HTTP errors (404/500), -s is silent
until curl -f -s ${HEALTH_CHECK_URL} > /dev/null; do
  current_time=$(date +%s)
  elapsed_time=$((current_time - start_time))
  
  if [ $elapsed_time -ge $TIMEOUT ]; then
    echo "❌ Timeout (${TIMEOUT}s) reached. Backend service not ready."
    echo "   FATAL ERROR: Org360 UI will not start without a healthy backend API."
    exit 1
  fi
  
  echo "   ... waiting (${elapsed_time}s elapsed)"
  sleep $INTERVAL
done

echo "✅ Backend service is healthy. Starting Nginx..."

# Execute the main Nginx entrypoint command
exec /docker-entrypoint.sh "$@"