// src/contexts/CustomizationContext.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'; 
import { useAuth } from './AuthContext'; 
import { theme as tokens } from '../theme'; // Assuming tokens is available

const CustomizationContext = createContext(null);

export const useCustomization = () => useContext(CustomizationContext);

// Default structure for HSL and Dimensionality
const DEFAULT_HSL = { hue: 200, saturation: 90, lightness: 55, dimensionalityScore: 0.5 };
const DEFAULT_LAYOUT = []; 

export const CustomizationProvider = ({ children }) => {
    // CRITICAL FIX 1: Use defensive hook access
    const { user, userRole, isAuthenticated, isLoading } = useAuth() || {}; 
    
    // Orchestrator result states used by AI_UI_Commander (new)
    const [orchestratorResultId, setOrchestratorResultId] = useState(null); 
    const [orchestratorPrompt, setOrchestratorPrompt] = useState(''); 

    // 1. COMMITTED STATE (Saved and permanent)
    const [committedThemeHSL, setCommittedThemeHSL] = useState(() => {
        try {
            const saved = localStorage.getItem('hiro_committed_hsl');
            return saved ? JSON.parse(saved) : DEFAULT_HSL;
        } catch { return DEFAULT_HSL; }
    });
    const [committedLayout, setCommittedLayout] = useState(() => {
        try {
            const saved = localStorage.getItem('hiro_committed_layout');
            return saved ? JSON.parse(saved) : DEFAULT_LAYOUT;
        } catch { return DEFAULT_LAYOUT; }
    });
    const [committedDensity, setCommittedDensity] = useState(() => {
        return localStorage.getItem('hiro_committed_density') || 'standard';
    });

    // 2. TEMPORARY/DYNAMIC STATES
    const [pendingConfig, setPendingConfig] = useState(null); // AI Preview (Theme/Layout)
    const [synthesizedDashboardConfig, setSynthesizedDashboardConfig] = useState(null); // The dynamic report config 

    // CRITICAL FIX 2: useMemo explicitly used for user context derivation
    const userContext = useMemo(() => ({
        userId: user?.id, 
        userRole: userRole,
        isAuthenticated: isAuthenticated
    }), [user?.id, userRole, isAuthenticated]);

    // 3. DERIVED ACTIVE STATE (Used by all components for rendering)
    const activeThemeHSL = useMemo(() => pendingConfig?.themeHSL || committedThemeHSL || DEFAULT_HSL, [pendingConfig, committedThemeHSL]);
    const activeLayout = useMemo(() => pendingConfig?.layoutChanges || committedLayout || DEFAULT_LAYOUT, [pendingConfig, committedLayout]);
    const activeDensity = useMemo(() => pendingConfig?.uiDensity || committedDensity || 'standard', [pendingConfig, committedDensity]);
    
    // CRITICAL FIX 3: useCallback explicitly used for committing config
    const commitConfig = useCallback(() => {
        if (!pendingConfig) return;
        setCommittedThemeHSL(pendingConfig.themeHSL);
        setCommittedLayout(pendingConfig.layoutChanges);
        setCommittedDensity(pendingConfig.uiDensity);
        
        try {
            localStorage.setItem('hiro_committed_hsl', JSON.stringify(pendingConfig.themeHSL));
            localStorage.setItem('hiro_committed_layout', JSON.stringify(pendingConfig.layoutChanges));
            localStorage.setItem('hiro_committed_density', pendingConfig.uiDensity);
        } catch (e) {
            console.error("Failed to persist theme configuration", e);
        }

        setPendingConfig(null); 
        console.log("Config Committed and Persisted to localStorage!");
    }, [pendingConfig]);

    // CRITICAL FIX 4: useCallback explicitly used for reverting config
    const revertConfig = useCallback(() => {
        setPendingConfig(null);
    }, []);

    // Theme Application Effect (Applies HSL and Dimensionality variables to CSS)
    useEffect(() => {
        // CRITICAL FIX 5: Ensure required CSS variables are set
        const applyTheme = (hsl) => {
            document.documentElement.style.setProperty('--user-hue', `${hsl.hue}`);
            document.documentElement.style.setProperty('--saturation', `${hsl.saturation}%`);
            document.documentElement.style.setProperty('--lightness', `${hsl.lightness}%`);
            document.documentElement.style.setProperty('--dimensionality-score', `${hsl.dimensionalityScore}`); 
            document.documentElement.setAttribute('data-density', activeDensity);
            document.documentElement.style.setProperty('--holo-primary', `hsl(${hsl.hue}, ${hsl.saturation}%, ${hsl.lightness}%)`);
        };

        if (activeThemeHSL) {
            applyTheme(activeThemeHSL);
        } else {
            applyTheme(DEFAULT_HSL);
        }
    }, [activeThemeHSL, activeDensity]);

    // CRITICAL FIX 6: useMemo explicitly used for provider value
    const value = useMemo(() => ({
        userContext, 
        activeThemeHSL, activeLayout, activeDensity,
        synthesizedDashboardConfig, 
        setSynthesizedDashboardConfig,
        setPendingConfig, 
        commitConfig, 
        revertConfig, 
        isPreviewing: !!pendingConfig,
        orchestratorResultId, // New states for tracking async jobs
        setOrchestratorResultId,
        orchestratorPrompt,
        setOrchestratorPrompt
    }), [
        userContext, activeThemeHSL, activeLayout, activeDensity, 
        synthesizedDashboardConfig, setSynthesizedDashboardConfig, setPendingConfig, 
        commitConfig, revertConfig, pendingConfig, orchestratorResultId, 
        orchestratorPrompt
    ]);

    if (isLoading) {
        return null; // Wait for AuthContext to load
    }

    return (
        <CustomizationContext.Provider value={value}>
            {children}
        </CustomizationContext.Provider>
    );
};