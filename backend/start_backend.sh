#!/bin/bash
#============================================================================
# HiRo BACKEND CONTAINER STARTUP SCRIPT - PRODUCTION READY
# Replaced Uvicorn direct exec with Gunicorn for worker management.
#============================================================================

set -euo pipefail

echo "================================================="
echo " 🚀 HiRo Backend Container Startup (Production)"
echo "================================================="

# CRITICAL FIX 1: Explicitly export the correct URL derived from .env or docker-compose
# This ensures Python scripts can access the full connection string set in the environment.
export POSTGRES_URL="${POSTGRES_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}}"
export MONGO_URL="${MONGO_URL:-mongodb://${MONGO_USER}:${MONGO_PASSWORD}@${MONGO_HOST}:${MONGO_PORT}/${MONGO_DB_NAME}?authSource=admin}"
export NATS_URL="${NATS_URL:-nats://nats:4222}" # Ensure NATS URL is also exported

echo " 📝 Database URLs set. Waiting for readiness..."

# --- Wait for Infrastructure to be TRULY Ready using Python's DB Waiter ---
# The Python waiter handles retries and full checks for Mongo, Redis, Postgres, NATS, and Dgraph (optional).
# Prefer module invocation so Python package resolution is consistent.
# CRITICAL FIX 2: Ensure we are using the enhanced db_waiter logic
if python -m utils.db_waiter; then
    echo " ✅ All network databases and services are READY."
else
    echo " ❌ CRITICAL: Database readiness check failed. Exiting."
    exit 1
fi

echo " ⚙️ Initializing/seeding database and test users for investor demo..."
# CRITICAL FIX 3: Running the master initialization script which includes demo data seeding
if python /app/init_test_data.py; then
    echo " ✅ Database initialization and INVESTOR DEMO users/data are READY."
else
    echo " ❌ CRITICAL: Database seeding failed. Exiting."
    exit 1
fi

echo " 🚀 Starting Gunicorn server with Uvicorn workers..."
# Execute Gunicorn, replacing the script process with the server process.
# -c /app/gunicorn_conf.py uses the fixed configuration for worker settings. [cite: 1264]
# server:app specifies the ASGI application entry point from server.py.
exec gunicorn -c /app/gunicorn_conf.py server:app