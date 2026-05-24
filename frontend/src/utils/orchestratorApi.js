// src/utils/orchestratorApi.js - FINAL PRODUCTION-READY STABILIZATION

import UISchema from '../config/UISchema.json'; 
import SynthesizedDashboardSchema from '../config/SynthesizedDashboardSchema.json';
// CRITICAL FIX 1: Import the new runOrchestrationCommand from the centralized API file
import { post, runOrchestrationCommand as runOrchestrationCommandApi } from '../config/api'; 

// CRITICAL FIX 2: Orchestrator URL is now just used for context, but not for direct fetch
// Backend Orchestrator calls should now use the API client or the dedicated functions.
const ORCHESTRATOR_URL = process.env.REACT_APP_ORCHESTRATOR_API_URL || '/api/orchestrator';

/**
 * Helper for generating structured configs (UI or Dashboard) by sending the prompt 
 * and the required JSON schema to the orchestrator endpoint via the centralized POST utility.
 * @param {string} endpoint - The specific orchestrator sub-endpoint (/generate-ui-config or /synthesize-dashboard)
 * @param {object} payload - The core data payload (prompt, context, current config)
 * @param {object} schema - The required JSON schema (UISchema or SynthesizedDashboardSchema)
 * @param {number} retries - Retry count (handled defensively by Axios interceptor, but retained for fetch safety)
 */
const fetchConfig = async (endpoint, payload, schema, retries = 1) => { // Removed redundant retries as Axios handles it
    // CRITICAL FIX 3: Use the centralized API POST utility
    // We send the full, required payload, including the JSON schema for LLM instruction.
    const response = await post(`${ORCHESTRATOR_URL}${endpoint}`, { 
        ...payload, 
        schema_for_llm: schema 
    });

    // Axios response structure is response.data
    const data = response.data;

    if (!data.generated_config) {
        // Explicit check for a structured config from the AI response
        throw new Error("Orchestrator did not return a valid structured configuration for the schema.");
    }
    
    return data.generated_config; 
};


// 1. Used by AI Commander for Theme/Layout Micro-Adjustments
export async function generateUIConfig(prompt, currentConfig) {
    return fetchConfig('/generate-ui-config', { prompt, current_config: currentConfig }, UISchema);
}

// 2. Used by AI Commander for Dashboard Synthesis
export async function generateDashboardConfig(prompt, userContext) {
    try {
        // Attempt to get a structured dashboard config
        return await fetchConfig('/synthesize-dashboard', { prompt, user_context: userContext }, SynthesizedDashboardSchema);
    } catch (error) {
        // If the specific synthesis endpoint fails (e.g., 404), fall back to a general UI config request
        if (error.response && (error.response.status === 404 || error.response.status === 422)) {
            console.warn('Fallback: Synthesize-dashboard failed. Using general orchestrator for UI config.');
            // Send a modified prompt to the general UI configuration endpoint
            return await fetchConfig('/generate-ui-config', { 
                prompt: `Synthesize data structure for a dashboard based on: ${prompt}`, 
                current_config: {} 
            }, UISchema);
        }
        throw error;
    }
}

/**
 * CRITICAL NEW CONTRACT (ID 1): Executes an asynchronous orchestration command.
 * This is the function called by AI_UI_Commander.js.
 * It uses the production-ready API function defined in api.js.
 * @param {string} prompt - The natural language command.
 * @param {object} userContext - The user's ID and role.
 * @returns {Promise<object>} - A promise resolving to the response, which should contain the result_id.
 */
export async function runOrchestrationCommand(prompt, userContext) {
    // CRITICAL FIX 4: Use the imported production API function
    return runOrchestrationCommandApi(prompt, userContext);
}