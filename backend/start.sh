#!/bin/bash
# ============================================================================
# ORG360 BACKEND CONTAINER STARTUP SCRIPT
# Executes inside the 'org360-backend' container.
# ============================================================================
set -e

echo "================================================="
echo "   Org360 Backend Container Startup"
echo "================================================="

# --- Wait for Infrastructure to be TRULY Ready using Python's DB Waiter ---
echo "⏳ Waiting for Mongo, Redis, and Postgres/NATS to be READY using Python waiter..."
# CRITICAL FIX: The file path reflects the COPY command in the Dockerfile
# NOTE: You MUST update db_waiter.py to check Postgres and NATS instead of Dgraph/Ollama.
python /app/utils/db_waiter.py

# Check the exit code of the Python script
if [ $? -ne 0 ]; then
    echo "❌ CRITICAL: Database/Infrastructure readiness check failed. Exiting."
    exit 1
fi
echo "✅ All network infrastructure (Mongo, Redis, Postgres, NATS) is READY."

# --- AI Model Check and Pull (DEPRECATED - Moved to API calls) ---
echo "✅ AI services are now using Groq/Gemini APIs; skipping local model checks."

# --- Database Initialization / Seeding ---
echo "⚙️ Initializing/seeding database..."
# Run the application's initialization script (e.g., setting up collections, indexes, test data)
# CRITICAL FIX: Corrected path for init_test_data.py
python /app/init_test_data.py

echo "🚀 Starting Gunicorn server..."
# Execute Gunicorn, replacing the script process with the server process.
# -c /app/gunicorn_conf.py: Uses the configuration file for worker settings.
# server:app: Specifies the ASGI application entry point (e.g., from server.py import app).
exec gunicorn -c /app/gunicorn_conf.py server:app