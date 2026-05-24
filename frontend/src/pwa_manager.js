// /frontend/src/pwa_manager.js - FINAL PRODUCTION-READY REPLACEMENT (PWA MANAGER)

/**
 * Progressive Web App Manager
 * Initializes the Service Worker for offline capabilities and caching.
 */

const isLocalhost = Boolean(
    window.location.hostname === 'localhost' ||
    // [::1] is the IPv6 localhost address.
    window.location.hostname === '[::1]' ||
    // 127.0.0.0/8 are considered localhost for IPv4.
    window.location.hostname.match(
        /^127(?:\.(?:0|25[0-5]|2[0-4]\d|1?\d\d?)){3}$/
    )
);

export function initServiceWorker() {
    if ('serviceWorker' in navigator) {
        // CRITICAL: Ensure the service worker is only registered in production or explicitly allowed environments
        if (process.env.NODE_ENV === 'production' || isLocalhost) {
            const swUrl = `${process.env.PUBLIC_URL}/service-worker.js`;

            navigator.serviceWorker.register(swUrl)
                .then(registration => {
                    console.log('PWA Service Worker registered:', registration);
                })
                .catch(error => {
                    console.error('PWA Service Worker registration failed:', error);
                });
        }
    }
}