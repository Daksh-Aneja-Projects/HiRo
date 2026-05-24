#!/usr/bin/env bash
set -euo pipefail

echo "=== Running Smoke Tests ==="

BASE_BACKEND_URL="http://localhost:8001"
FRONTEND_URL="http://localhost:80" # Assuming Nginx proxy runs on port 80

# 1) Backend Health Check (Requires Postgres/NATS to be up for lifespan hook to complete)
echo "1) Checking Backend Health -> ${BASE_BACKEND_URL}/api/health"
MAX_RETRIES=10
RETRY_COUNT=0
while ! curl -sSf "${BASE_BACKEND_URL}/api/health" >/dev/null 2>&1; do
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "❌ Backend health failed after $MAX_RETRIES attempts."
    # Check the logs of the critical dependencies (Postgres and Backend)
    docker compose logs backend postgres_db nats --tail=50
    exit 1
  fi
  echo "⏳ Backend not ready yet. Retrying in 5s... ($RETRY_COUNT/$MAX_RETRIES)"
  sleep 5
  RETRY_COUNT=$((RETRY_COUNT+1))
done
echo "✅ Backend: OK"


# 2) API Auth Check
PROTECTED_URL="${BASE_BACKEND_URL}/api/hr/leave/balance"
echo "2) API Auth Check -> ${PROTECTED_URL} (Expect 401/403)"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${PROTECTED_URL}")
if [[ "$STATUS" == "401" || "$STATUS" == "403" ]]; then
  echo "✅ Auth Check: OK (HTTP $STATUS)"
else
  echo "❌ Auth Check: FAILED (Expected 401/403, got $STATUS)"
  exit 1
fi

# 3) Frontend Availability
echo "3) Checking Frontend -> ${FRONTEND_URL}"
RETRY_COUNT=0
while ! curl -sSf "${FRONTEND_URL}" >/dev/null 2>&1; do
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "❌ Frontend test failed after $MAX_RETRIES attempts."
    docker compose logs nginx_proxy --tail=50 
    exit 1
  fi
  echo "⏳ Frontend not ready yet. Retrying in 5s... ($RETRY_COUNT/$MAX_RETRIES)"
  sleep 5
  RETRY_COUNT=$((RETRY_COUNT+1))
done
echo "✅ Frontend: OK"

echo "=== Smoke Tests Completed ==="