// /frontend/src/utils/app-utils.js - FINAL PRODUCTION-READY REPLACEMENT (UTILITIES)

/**
 * Collection of application-specific, non-React utilities.
 */

// Example utility: Format date consistently across the app
export const formatAppDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch (e) {
        return dateString;
    }
};

// Example utility: Simple sleep function
export const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));