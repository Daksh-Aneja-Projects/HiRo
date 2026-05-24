// /frontend/src/service-worker.js

const CACHE_NAME = 'org360-cache-v6'; // Increment version for fresh install
const CORE_ASSETS = [
  // The app shell: index.html is the core fallback
  '/',
  '/index.html',
  '/manifest.json',
  '/logo.svg', 
  '/logo192.png'
];

// 1. Install Event: Populate cache with core assets
self.addEventListener('install', (event) => {
  console.log('👷 Service Worker: Installing cache:', CACHE_NAME);
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        // CRITICAL FIX: Robustly cache all core assets except the root path, which is manually handled
        const assetsToCache = CORE_ASSETS.filter(url => url !== '/');

        // Robust, fault-tolerant Promise.all fetch/put
        const addAllPromises = assetsToCache.map(url => {
            return fetch(url, { cache: "no-store" }) 
                .then(response => {
                    if (!response || response.status !== 200 || response.type === 'opaque') {
                        console.warn(` ⚠️ SW: Skipping caching ${url}. Received status ${response ? response.status : 'No Response'}.`);
                        return Promise.resolve(); 
                    }
                    return cache.put(url, response.clone());
                })
                .catch(error => {
                    console.warn(` ⚠️ SW: Could not fetch or cache ${url}. Skipping failed resource: ${error.message}`);
                    return Promise.resolve();
                });
        });
        
        // Manually cache the root path as an alias for index.html
        return Promise.all(addAllPromises).then(() => {
             return caches.match('/index.html').then(response => {
                 if (response) {
                     return cache.put('/', response);
                 }
                 return Promise.resolve();
             });
        });
      })
      .then(() => self.skipWaiting())
      .catch(error => {
        console.error(' ❌ SW: Cache installation failed (top-level error):', error);
      })
  );
});

// 2. Activate Event: Clean up old caches (Logic is fine, kept for completeness)
self.addEventListener('activate', (event) => {
  console.log(' 🔥 Service Worker: Activating and cleaning old caches.');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
          return null;
        })
      );
    }).then(() => self.clients.claim())
  );
});

// 3. Fetch Event: Robust Routing and Caching Strategies
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // CRITICAL FIX: Network-Only for API/WS/External Traffic
  const isApi = url.pathname.startsWith('/api/') || url.pathname.startsWith('/ollama') || url.pathname.startsWith('/ws/');
  const isExternal = url.origin !== location.origin;

  if (isApi || isExternal) {
    event.respondWith(fetch(event.request).catch(() => {
      // If API fails AND it's a primary document request (like navigating to an SPA route), serve app shell
      if (event.request.mode === 'navigate' || url.pathname === '/') {
        console.log('⚠️ SW: API failed. Serving app shell fallback.');
        return caches.match('/index.html');
      }
      throw new Error('API/External request failed, offline.');
    }));
    return;
  }

  // Strategy: Cache-First, falling back to network, with App Shell for navigation
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      // Return cached asset immediately if available
      if (cachedResponse) {
          // Optional: Update cache in background (Stale-While-Revalidate pattern)
          const networkFetch = fetch(event.request).then(networkResponse => {
              if (networkResponse && networkResponse.status === 200) {
                  caches.open(CACHE_NAME).then(cache => cache.put(event.request, networkResponse.clone()));
              }
              return networkResponse;
          }).catch(() => { /* Network update failed */ });
          
          return cachedResponse;
      }
      
      // If cache miss: go to network
      return fetch(event.request).catch(() => {
          // CRITICAL FIX: If fetch fails and it's a navigation request, serve the App Shell.
          if (event.request.mode === 'navigate') {
              console.log('⚠️ SW: Network failed. Serving app shell fallback.');
              return caches.match('/index.html');
          }
          throw new Error('Network request failed, offline.');
      });
    })
  );
});

// 4. Message Listener (Logic is fine, kept for completeness)
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});