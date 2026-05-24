#!/bin/bash
# ===================================================================
# ORG360 ENVIRONMENT GENERATOR - MOTHER OF ALL TRUTH
# Generates backend/.env and frontend/.env from root .env
# ===================================================================

set -e

echo "🔧 Generating environment files from root .env..."

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_ENV="$ROOT_DIR/.env"
BACKEND_ENV="$ROOT_DIR/backend/.env"
FRONTEND_ENV="$ROOT_DIR/frontend/.env"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Check if root .env exists
if [ ! -f "$ROOT_ENV" ]; then
    echo "❌ Root .env file not found at: $ROOT_ENV"
    echo "📝 Creating template root .env..."
    cp "$ROOT_DIR/.env.example" "$ROOT_ENV"
fi

# Create header for backend .env
cat > "$BACKEND_ENV" << EOF
# ===================================================================
# BACKEND ENVIRONMENT - AUTO-GENERATED FROM ROOT .env
# DO NOT EDIT MANUALLY - Use root .env as single source of truth
# ===================================================================

# Generated: $TIMESTAMP
# Source: .env (root)

EOF

# Filter and copy backend variables
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# CORE APPLICATION SETTINGS" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(HOST|PORT|ENV|LOG_LEVEL|APP_NAME|APP_VERSION)=' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# DATABASE CONFIGURATION" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(MONGO_|POSTGRES_|DGRAPH_|REDIS_)' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# NATS JETSTREAM (Message Bus)" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(NATS_)' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# AI SERVICES CONFIGURATION" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(GEMINI_|GROQ_|OLLAMA_)' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# SECURITY & AUTHENTICATION" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(JWT_|ADMIN_|DEFAULT_TEST_PASSWORD|PII_SALT|AGENT_SIGNING_SECRET|HRIT_MANAGER_APPROVERS)=' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# TEST CREDENTIALS (THREE USERS)" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(TEST_)' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# FRONTEND CONFIGURATION" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(FRONTEND_|ENABLE_CORS|CORS_ALLOWED_ORIGINS)=' "$ROOT_ENV" >> "$BACKEND_ENV"

echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# APPLICATION CONFIGURATION" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -E '^(RATE_LIMIT_|MAX_BODY_SIZE_|POLICY_|DTLA_|EXTERNAL_API_)' "$ROOT_ENV" >> "$BACKEND_ENV"

# Copy all other non-REACT_APP variables
echo "" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
echo "# ALL OTHER CONFIGURATION" >> "$BACKEND_ENV"
echo "# =====================================================" >> "$BACKEND_ENV"
grep -v '^REACT_APP_' "$ROOT_ENV" | grep -v '^#' | grep -v '^$' | grep -v '^TEST_' | \
    grep -v '^HOST=' | grep -v '^PORT=' | grep -v '^ENV=' | grep -v '^LOG_LEVEL=' | \
    grep -v '^APP_NAME=' | grep -v '^APP_VERSION=' | \
    grep -v '^MONGO_' | grep -v '^POSTGRES_' | grep -v '^DGRAPH_' | grep -v '^REDIS_' | \
    grep -v '^NATS_' | grep -v '^GEMINI_' | grep -v '^GROQ_' | grep -v '^OLLAMA_' | \
    grep -v '^JWT_' | grep -v '^ADMIN_' | grep -v '^DEFAULT_TEST_PASSWORD=' | \
    grep -v '^PII_SALT=' | grep -v '^AGENT_SIGNING_SECRET=' | grep -v '^HRIT_MANAGER_APPROVERS=' | \
    grep -v '^FRONTEND_' | grep -v '^ENABLE_CORS=' | grep -v '^CORS_ALLOWED_ORIGINS=' | \
    grep -v '^RATE_LIMIT_' | grep -v '^MAX_BODY_SIZE_' | grep -v '^POLICY_' | \
    grep -v '^DTLA_' | grep -v '^EXTERNAL_API_' >> "$BACKEND_ENV"

# Create frontend .env
cat > "$FRONTEND_ENV" << EOF
# ===================================================================
# FRONTEND ENVIRONMENT - AUTO-GENERATED FROM ROOT .env
# DO NOT EDIT MANUALLY - Use root .env as single source of truth
# ===================================================================

# Generated: $TIMESTAMP
# Source: .env (root)

# REACT_APP variables are embedded at build time
# Other variables are for Docker runtime

EOF

echo "# =====================================================" >> "$FRONTEND_ENV"
echo "# BACKEND API CONFIGURATION" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
grep -E '^REACT_APP_(BACKEND_URL|ORCHESTRATOR_API_URL|WS_URL)=' "$ROOT_ENV" >> "$FRONTEND_ENV"

echo "" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
echo "# FEATURE FLAGS" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
grep -E '^REACT_APP_ENABLE_' "$ROOT_ENV" >> "$FRONTEND_ENV"

echo "" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
echo "# SECURITY KEYS (Embedded at build time)" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
grep -E '^REACT_APP_(JWT_SECRET|GEMINI_API_KEY)=' "$ROOT_ENV" >> "$FRONTEND_ENV"

echo "" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
echo "# TEST CREDENTIALS INFO (For UI display)" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
grep -E '^TEST_.*USERNAME=' "$ROOT_ENV" | sed 's/^TEST_/REACT_APP_TEST_/' >> "$FRONTEND_ENV"

echo "" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
echo "# SI INTEGRATION CONFIGURATION" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
cat >> "$FRONTEND_ENV" << EOF
REACT_APP_SI_INTEGRATION_ENABLED=true
REACT_APP_WEBSOCKET_ENABLED=true
REACT_APP_STREAMING_ENABLED=true
REACT_APP_TELEMETRY_ENABLED=true
EOF

echo "" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
echo "# APPLICATION METADATA" >> "$FRONTEND_ENV"
echo "# =====================================================" >> "$FRONTEND_ENV"
cat >> "$FRONTEND_ENV" << EOF
REACT_APP_NAME=Org360
REACT_APP_VERSION=4.0.0
REACT_APP_ENV=production
REACT_APP_BUILD_TIMESTAMP=$(date +%s)
EOF

echo "✅ Generated backend/.env"
echo "✅ Generated frontend/.env"
echo ""
echo "📋 Summary:"
echo "   Root .env: $ROOT_ENV"
echo "   Backend .env: $BACKEND_ENV"
echo "   Frontend .env: $FRONTEND_ENV"
echo ""
echo "🔑 Test Credentials Summary:"
echo "   • admin/admin → Full system access (Admin Portal)"
echo "   • manager/manager → Team management access (Manager Portal)"
echo "   • demo/demo → Employee self-service (Employee Portal)"
echo ""
echo "🚀 To apply changes:"
echo "   1. docker-compose down"
echo "   2. docker-compose up -d --build"
echo "   3. ./reset_test_users.py"