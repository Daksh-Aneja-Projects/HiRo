// /frontend/src/utils/utils.js - FINAL PRODUCTION-READY REPLACEMENT (GENERIC UTILITIES)

/**
 * Collection of generic utilities (used as a fallback module).
 */

// Example utility: Deep clone object
export const deepClone = (obj) => {
    try {
        return JSON.parse(JSON.stringify(obj));
    } catch (e) {
        return obj; // Return original on error
    }
};

// Example utility: Debounce function
export const debounce = (func, delay) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
};