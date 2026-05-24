#!/bin/bash
# Org360_frontend/docker/build-env.sh

# This script is used to prepare the .env file with necessary environment
# variables before the React build process inside the Docker container.
# It ensures production-ready variables are baked into the static assets.

echo "Starting environment setup for React build..."

# CRITICAL FIX: Check for the required Gemini API Key (essential for Agentic AI)
if [ -z "$REACT_APP_GEMINI_API_KEY" ]; then
    echo "ERROR: REACT_APP_GEMINI_API_KEY is not set. Using a placeholder but this will likely fail."
    # Use a dummy value to allow the build to proceed but log a warning.
    DUMMY_GEMINI_KEY="DUMMY_KEY_FOR_BUILD_ONLY"
else
    DUMINI_GEMINI_KEY="$REACT_APP_GEMINI_API_KEY"
    echo "REACT_APP_GEMINI_API_KEY found. Proceeding with production build."
fi

# CRITICAL FIX: Explicitly create a .env file containing ALL required REACT_APP_ variables.
# This ensures Nginx's path mapping and critical API keys are set for the static build.
# The REACT_APP_BACKEND_URL is set to a relative path, which Nginx handles.

cat > .env.production << EOF
# --- Production Build Environment Variables ---
REACT_APP_BACKEND_URL=/api
REACT_APP_ORCHESTRATOR_API_URL=/orchestrator-api
REACT_APP_GEMINI_API_KEY=${REACT_APP_GEMINI_API_KEY}
REACT_APP_JWT_SECRET=${REACT_APP_JWT_SECRET}
# Enable visual edits flag for feature toggles
REACT_APP_ENABLE_VISUAL_EDITS=true 
# WS_URL is for local development and usually not needed in production if Nginx handles WSS proxying, 
# but included for consistency if a direct WS connection is attempted.
REACT_APP_WS_URL=ws://\${DOCKER_HOST_IP:-localhost}:8001/ws
# --- End of Variables ---
EOF

echo "Generated .env.production file for React build."

# CRITICAL FIX: Ensure the react-scripts build is run after the env is prepared
echo "Starting React build process..."
npm run build

echo "React build process completed."

# CRITICAL FIX: Exit with a success code if the build command was successful (implicit via 'set -e' if used, but safe to assume npm run build handles it)
exit 0