// /frontend/src/setupProxy.js - FINAL PRODUCTION-READY REPLACEMENT (DEV PROXY)
const { createProxyMiddleware } = require('http-proxy-middleware');

// CRITICAL FIX: Define the backend target URL here. 
// NOTE: In a real-world scenario, this URL would come from an environment variable.
const BACKEND_TARGET = process.env.BACKEND_PROXY_URL || 'http://localhost:8000'; 

module.exports = function(app) {
    // 1. Proxy API endpoints (everything starting with /api)
    app.use(
        '/api',
        createProxyMiddleware({
            target: BACKEND_TARGET,
            changeOrigin: true,
            // Path rewrite is usually not necessary if the backend also uses /api
        })
    );
    
    // 2. Proxy WebSocket connections (crucial for LiveTelemetryFeed)
    // CRITICAL FIX: Route all /ws/si-integration traffic to the backend target as a WebSocket
    app.use(
        '/ws/si-integration',
        createProxyMiddleware({
            target: BACKEND_TARGET,
            changeOrigin: true,
            ws: true, // CRITICAL: Enables WebSocket proxying
        })
    );
};