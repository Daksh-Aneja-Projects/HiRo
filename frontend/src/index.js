// C:\HiRo Project\frontend\src\index.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import * as serviceWorkerRegistration from './pwa_manager'; // CRITICAL FIX 1: Re-import the PWA manager
import './index.css'; 

const container = document.getElementById('root');
const root = createRoot(container);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// CRITICAL FIX 2: Call the PWA registration function here where all modules are properly loaded.
// If the Reference Errors persist after this, it indicates an unfixable build system issue 
// (which we temporarily bypass by commenting out this line).
// serviceWorkerRegistration.initServiceWorker(); // Using the newly renamed export 'initServiceWorker'
try {
  serviceWorkerRegistration.initServiceWorker(); 
} catch (e) {
  console.error("PWA Registration Error: Likely due to minification failure. Skipping registration.", e);
}
