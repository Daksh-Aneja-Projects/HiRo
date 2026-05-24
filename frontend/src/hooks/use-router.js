// /frontend/src/hooks/use-router.js - FINAL PRODUCTION-READY REPLACEMENT
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { useCallback, useMemo } from 'react';

/**
 * Custom hook to consolidate core routing functionalities.
 */
export const useRouter = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const params = useParams();

    // Utility to get a specific query parameter
    const getQueryParam = useCallback((key) => {
        return new URLSearchParams(location.search).get(key);
    }, [location.search]);

    // Utility to navigate with optional state
    const goTo = useCallback((path, options = {}) => {
        navigate(path, options);
    }, [navigate]);

    // Utility to push a new query parameter while preserving existing ones
    const setQueryParam = useCallback((key, value) => {
        const searchParams = new URLSearchParams(location.search);
        if (value) {
            searchParams.set(key, value);
        } else {
            searchParams.delete(key);
        }
        navigate(`${location.pathname}?${searchParams.toString()}`, { replace: true });
    }, [location.pathname, location.search, navigate]);

    return useMemo(() => ({
        navigate: goTo,
        location,
        params,
        getQueryParam,
        setQueryParam,
    }), [goTo, location, params, getQueryParam, setQueryParam]);
};