// /frontend/src/hooks/useApi.js
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useToast } from './use-toast';
import { createCancelToken } from '../config/api';
import axios from 'axios';

/**
 * Generalized API data fetching hook.
 * @param {Function} apiFunction - API function returning an Axios promise.
 * @param {Array} dependencies - Spread as positional args into apiFunction AND used as re-fetch deps.
 * @param {boolean} immediate - Fetch on mount.
 * @param {number|boolean} pollingInterval - Poll every N ms. Anything that is not a
 *   positive finite number disables polling (guards against callers who mistake this
 *   slot for `initialData` and would otherwise create a 0ms request storm).
 * @param {any} initialData - Initial value for `data`.
 */
export const useApi = (apiFunction, dependencies = [], immediate = true, pollingInterval = false, initialData = null) => {
    const { toast } = useToast();

    // A caller passing [] or {} here means initialData, not an interval. Never poll on it.
    const intervalMs = (typeof pollingInterval === 'number' && Number.isFinite(pollingInterval) && pollingInterval > 0)
        ? pollingInterval
        : 0;

    const [data, setData] = useState(initialData);
    const [isLoading, setIsLoading] = useState(immediate);
    const [error, setError] = useState(null);
    const cancelTokenRef = useRef(null);
    const hasLoadedRef = useRef(false);

    // Keep the latest toast/initialData without re-creating `fetch` on every render.
    const toastRef = useRef(toast);
    toastRef.current = toast;
    const initialDataRef = useRef(initialData);

    const depsKey = JSON.stringify(dependencies ?? []);

    const fetch = useCallback(async (extraParams = {}) => {
        if (cancelTokenRef.current) {
            cancelTokenRef.current.cancel('Superseded by a newer request.');
        }
        cancelTokenRef.current = createCancelToken();

        // Only flash the spinner before the first successful load; polling stays silent.
        if (!hasLoadedRef.current) setIsLoading(true);
        setError(null);

        try {
            const args = JSON.parse(depsKey);
            const response = await apiFunction(...args, {
                cancelToken: cancelTokenRef.current.token,
                ...extraParams,
            });

            hasLoadedRef.current = true;
            setData(response.data);
            setIsLoading(false);
            return response.data;
        } catch (err) {
            if (axios.isCancel(err)) return;

            const errorMessage = err.response?.data?.detail || err.message || `${apiFunction.name} failed`;
            setError(errorMessage);
            setIsLoading(false);

            // Background polls fail quietly; the error state is enough for the UI.
            if (!intervalMs) {
                toastRef.current({
                    title: 'Could not load data',
                    description: errorMessage,
                    variant: 'destructive',
                });
            }
            return undefined;
        }
    }, [apiFunction, depsKey, intervalMs]);

    useEffect(() => {
        if (immediate) fetch();

        // Polling lives here, not in fetch()'s finally block, so manual refetches
        // cannot stack multiple intervals on top of each other.
        let timer = null;
        if (intervalMs) timer = setInterval(fetch, intervalMs);

        return () => {
            if (timer) clearInterval(timer);
            if (cancelTokenRef.current) cancelTokenRef.current.cancel('Component unmounted.');
        };
    }, [fetch, immediate, intervalMs]);

    return useMemo(() => ({
        data,
        isLoading,
        error,
        refetch: fetch,
        isSuccess: !isLoading && !error && data !== initialDataRef.current,
    }), [data, isLoading, error, fetch]);
};
