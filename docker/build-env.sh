#!/bin/bash
# HiRo_frontend/docker/build-env.sh

# This script is used to prepare the .env file with necessary environment
# variables before the React build process inside the Docker container.
# It ensures production-ready variables are baked into the static assets.

echo "Starting environment setup for React build..."

# Create the .env file with the REACT_APP_ variables the static build needs.
# LLM inference is server-side via Ollama, so no AI keys are baked into the frontend.

cat > .env.production << EOF
# --- Production Build Environment Variables ---
REACT_APP_BACKEND_URL=/api
REACT_APP_ORCHESTRATOR_API_URL=/orchestrator-api
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