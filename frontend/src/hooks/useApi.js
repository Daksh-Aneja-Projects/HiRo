// /frontend/src/hooks/useApi.js - FINAL PRODUCTION-READY REPLACEMENT
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useToast } from './use-toast';
import { createCancelToken } from '../config/api'; // Assuming createCancelToken is exported from api.js
import axios from 'axios'; // Required to check for cancellation errors

/**
 * Custom Hook for generalized, production-ready API data fetching.
 * Handles loading states, errors, memoization of API functions, and request cancellation.
 * @param {Function} apiFunction - The API function to call (e.g., api.getEmployees). Must return an Axios Promise.
 * @param {Array} dependencies - Dependencies for re-fetching (similar to useEffect).
 * @param {boolean} immediate - If true, fetches data immediately on mount.
 * @param {number|boolean} pollingInterval - Interval in milliseconds for polling, or false to disable.
 * @param {any} initialData - Initial state for the data.
 */
export const useApi = (apiFunction, dependencies = [], immediate = true, pollingInterval = false, initialData = null) => {
    // CRITICAL FIX 1: Explicitly define all state and hooks
    const { toast } = useToast();
    const [data, setData] = useState(initialData);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const cancelTokenRef = useRef(null);
    const intervalRef = useRef(null);

    // CRITICAL FIX 2: useCallback for the core fetch logic
    const fetch = useCallback(async (extraParams = {}) => {
        // Clear previous interval if this fetch is triggered manually/outside the interval loop
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
        }

        // 1. Setup Cancel Token
        if (cancelTokenRef.current) {
            cancelTokenRef.current.cancel('Previous request cancelled due to new fetch or unmount.');
        }
        cancelTokenRef.current = createCancelToken();
        
        // Only set loading state if data is not present (avoids UI flash during background polling)
        if (data === initialData) {
            setIsLoading(true);
        }
        setError(null);

        try {
            // CRITICAL FIX 3: Invoke the API function with its arguments
            const response = await apiFunction(...dependencies, { 
                cancelToken: cancelTokenRef.current.token, 
                ...extraParams 
            });

            setData(response.data);
            setIsLoading(false); // Ensure loading is cleared on success
            return response.data;

        } catch (err) {
            if (axios.isCancel(err)) {
                console.log('Request cancelled:', apiFunction.name);
                return;
            }

            // CRITICAL FIX 4: Extract meaningful error from Axios response
            const errorMessage = err.response?.data?.detail || err.message || `An unknown error occurred in ${apiFunction.name}`;
            
            setError(errorMessage);
            // Only show toast if it's not a background poll error
            if (immediate || !pollingInterval) {
                 toast({
                    title: `${apiFunction.name} Failed`,
                    description: errorMessage,
                    variant: 'destructive',
                });
            }
            setData(initialData); 
            throw err; 
            
        } finally {
            // Re-establish polling interval if enabled, but only after the first run
            if (pollingInterval) {
                intervalRef.current = setInterval(fetch, pollingInterval);
            }
        }
    }, [apiFunction, ...dependencies, initialData, toast, pollingInterval]);

    // 5. Initialization and Polling Effect
    useEffect(() => {
        if (immediate) {
            fetch(); // Initial fetch
        }
        
        // 6. Cleanup: Cancel any pending request on unmount
        return () => {
            if (cancelTokenRef.current) {
                cancelTokenRef.current.cancel('Component unmounted.');
            }
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [fetch, immediate, pollingInterval]);

    // CRITICAL FIX 7: useMemo for stable return object
    const memoizedReturn = useMemo(() => ({
        data,
        isLoading,
        error,
        refetch: fetch,
        // Helper flag for easy checking in components
        isSuccess: !isLoading && !error && data !== initialData
    }), [data, isLoading, error, fetch, initialData]);

    return memoizedReturn;
};