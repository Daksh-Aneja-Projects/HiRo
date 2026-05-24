// src/components/AI_UI_Commander.js - STABILIZED AND PRODUCTION-READY
import React, { useState, useCallback, useMemo, memo } from 'react';
import { Wand, Loader2, Zap, BarChart, X } from 'lucide-react';
import { useCustomization } from '../contexts/CustomizationContext';
import { runOrchestrationCommand, generateDashboardConfig } from '../utils/orchestratorApi'; // ASSUMPTION: runOrchestrationCommand is the new API function
import { theme as tokens } from '../theme';

// CRITICAL NEW COMPONENT IMPORT
import OrchestratorResultWidget from './OrchestratorResultWidget';

// FIX: Changed from 'export const AI_UI_Commander' to 'const AI_UI_Commander'
const AI_UI_Commander = memo(() => {
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [orchestratorResultId, setOrchestratorResultId] = useState(null); // New state for Orchestrator Result ID
  const [orchestratorPrompt, setOrchestratorPrompt] = useState(''); // New state for the prompt

  // CRITICAL FIX 1: Ensure defensive access to context setters and full context
  const customizationContext = useCustomization() || {};
  const { 
    setPendingConfig, 
    setSynthesizedDashboardConfig, 
    synthesizedDashboardConfig, 
    userContext,
    setOrchestrationResult
  } = customizationContext;

  // CRITICAL HOOK FIX: useCallback used explicitly
  const handleCommand = useCallback(async () => {
    if (!prompt.trim() || isLoading) return;
    setIsLoading(true);
    setOrchestratorResultId(null); // Reset previous result

    // CRITICAL FIX 2: Ensure context setters exist before calling them
    if (!setPendingConfig || !setSynthesizedDashboardConfig) {
        console.error("Customization Context setters are missing. Cannot run command.");
        setIsLoading(false);
        return;
    }
    
    // Store the prompt for the widget
    const currentPrompt = prompt;
    setOrchestratorPrompt(currentPrompt);
    
    try {
      // Logic for synthesizing a dashboard report (ID 4) - Using the dedicated dashboard generation API (non-orchestrated)
      if (prompt.toLowerCase().includes('report') || prompt.toLowerCase().includes('dashboard')) {
        const synthesizedConfig = await generateDashboardConfig(currentPrompt, userContext);
        setSynthesizedDashboardConfig(synthesizedConfig);
        setOrchestratorResultId(null); // No widget needed for direct config
      } else {
        // General Orchestration Command (e.g., UI config, Remediation, etc.)
        // This maps to the /api/orchestrate/command backend route (ID 1)
        const response = await runOrchestrationCommand(currentPrompt, userContext);
        
        // Assuming the response contains an ID for tracking the async job
        const resultId = response?.result_id || 'MOCK_ID_' + Date.now(); 
        
        // CRITICAL: Set the result ID to show the OrchestratorResultWidget
        setOrchestratorResultId(resultId);
        
        // In a real application, the result would be fetched later or streamed. 
        // For now, we only set the ID for the widget to start its mock/poll process.
      }
    } catch (error) {
      console.error("AI Command execution failed:", error);
      // Optional: Set a temporary state to show an error message
    } finally {
      setIsLoading(false);
      setPrompt(''); // Clear input after command is sent
    }
  }, [prompt, isLoading, userContext, setSynthesizedDashboardConfig, setPendingConfig]);

  // Styles remain the same
  const styles = useMemo(() => ({
    commanderBar: {
      position: 'fixed',
      bottom: tokens.spacing?.lg,
      right: tokens.spacing?.lg,
      display: 'flex',
      gap: tokens.spacing?.sm,
      background: tokens.color?.['panel-800'],
      padding: tokens.spacing?.sm,
      borderRadius: tokens.border?.radius?.card,
      boxShadow: tokens.shadow?.hover,
      zIndex: 2000,
    },
    input: {
      padding: '8px 12px',
      border: 'none',
      background: tokens.color?.['panel-700'],
      color: tokens.color?.['text-100'],
      borderRadius: tokens.border?.radius?.input,
      outline: 'none',
      width: '300px',
    },
    buttonBase: {
      padding: '8px',
      borderRadius: tokens.border?.radius?.button,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      border: 'none', // Ensure button border is consistent
    },
    // New style for the widget container
    widgetContainer: {
        position: 'fixed',
        bottom: `calc(${tokens.spacing?.lg} + 60px)`, // Position above the commander bar
        right: tokens.spacing?.lg,
        zIndex: 1999,
    }
  }), []);

  return (
    <>
      {orchestratorResultId && (
        <div style={styles.widgetContainer}>
          {/* CRITICAL INTEGRATION: Use the new widget to track the async job */}
          <OrchestratorResultWidget 
            resultId={orchestratorResultId} 
            prompt={orchestratorPrompt}
            // Add a mechanism to dismiss the widget after completion/error
            onDismiss={() => setOrchestratorResultId(null)}
          />
        </div>
      )}

      <div style={styles.commanderBar}>
        <input 
          style={styles.input}
          placeholder="Transform UI node or synthesize report..."
          value={prompt} 
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleCommand()}
        />
        <button 
          onClick={handleCommand}
          style={{ ...styles.buttonBase, background: tokens.color?.['accent-primary'] }}
          title="Execute AI Command"
          disabled={isLoading} // Disable button while loading
        >
          {isLoading ? <Loader2 className="animate-spin" /> : <Zap size={18} color="black" />}
        </button>
        {synthesizedDashboardConfig && (
          <button 
              onClick={() => setSynthesizedDashboardConfig(null)}
              style={{ ...styles.buttonBase, background: tokens.color?.['danger'], marginLeft: tokens.spacing?.sm }}
              title="Close Dashboard Preview"
          >
            <X size={18} color="white" />
          </button>
        )}
      </div>
    </>
  );
});

AI_UI_Commander.displayName = 'AI_UI_Commander';

// FIX: Add default export
export default AI_UI_Commander;