#!/bin/bash
# /frontend/docker/build-env.sh

set -e

# First, validate required environment variables
echo "🔍 Validating required environment variables..."

# CRITICAL FIX: Add all mission-critical variables to prevent runtime failures
REQUIRED_VARS=(
  "REACT_APP_BACKEND_URL"
  "REACT_APP_ORCHESTRATOR_API_URL"
)

for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var}" ]; then
    echo "❌ ERROR: $var is required but not set"
    exit 1
  fi
  echo "✅ $var: Set"
done

# CRITICAL FIX: Remove misleading URL validation check, as the path must be relative (/api) for proxying
# We only ensure the proxy URL is non-empty.

echo "🎬 Starting environment variable injection into React build files..."