// Whether this user wants live motion, and a way for them to change their mind.
//
// The OS-level "reduce motion" setting is global and is switched on for all
// sorts of reasons that have nothing to do with a preference about this app:
// Windows turns animations off on battery-saver and in several default power
// plans, and remote-desktop sessions report it too. Honouring it blindly froze
// the Neural Map completely, and a living map of the organisation that never
// moves is not a map anyone would call working.
//
// So the OS preference is the default, never the verdict. The user can override
// it per device and that choice sticks. Nothing here overrides the OS setting
// silently: a reduced-motion user gets a still map until they ask for movement.
import { useCallback, useEffect, useState } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';
const STORAGE_KEY = 'hiro_motion_preference'; // 'live' | 'calm' | absent = follow the OS

const osPrefersReduced = () =>
    typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(QUERY).matches;

const storedChoice = () => {
    try {
        return window.localStorage.getItem(STORAGE_KEY);
    } catch {
        // Private browsing and locked-down profiles throw on localStorage.
        // Falling back to the OS preference is the safe answer.
        return null;
    }
};

/**
 * Returns { reduced, source, setPreference, followSystem }.
 *   reduced      - true when motion should be held back right now
 *   source       - 'system' or 'user', so the UI can say which is in force
 *   setPreference('live' | 'calm')
 *   followSystem() - drop the override and go back to the OS setting
 */
export function useMotionPreference() {
    const [choice, setChoice] = useState(storedChoice);
    const [systemReduced, setSystemReduced] = useState(osPrefersReduced);

    // The OS setting can change while the app is open (unplugging a laptop is
    // enough to do it), so it is watched rather than read once at mount.
    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return undefined;
        const mq = window.matchMedia(QUERY);
        const onChange = (e) => setSystemReduced(e.matches);
        // Safari below 14 only has the deprecated listener API.
        if (mq.addEventListener) mq.addEventListener('change', onChange);
        else mq.addListener(onChange);
        return () => {
            if (mq.removeEventListener) mq.removeEventListener('change', onChange);
            else mq.removeListener(onChange);
        };
    }, []);

    const setPreference = useCallback((value) => {
        setChoice(value);
        try {
            window.localStorage.setItem(STORAGE_KEY, value);
        } catch {
            // The choice still applies for this session; it just will not persist.
        }
    }, []);

    const followSystem = useCallback(() => {
        setChoice(null);
        try {
            window.localStorage.removeItem(STORAGE_KEY);
        } catch {
            /* nothing to clean up */
        }
    }, []);

    const reduced = choice ? choice === 'calm' : systemReduced;

    return {
        reduced,
        source: choice ? 'user' : 'system',
        systemReduced,
        setPreference,
        followSystem,
    };
}

export default useMotionPreference;
