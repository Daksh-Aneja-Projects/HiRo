// src/utils/ai_client.js - STABILIZED & HOOKS-FIXED
// Unified AI Client - Proxies all requests to Backend

import { generateText as _apiGenerateText } from '../config/api';

const API_BASE = '/api/ai';

/** * Universal AI Call Handler via Backend 
 * @param {string} prompt 
 * @param {string} systemInstruction 
 * @param {number} retries 
 * @returns {Promise<string>} AI response text 
 */
async function callAI(prompt, systemInstruction = '', retries = 1) {
  const authToken = sessionStorage.getItem('authToken');
  if (!authToken) {
    throw new Error('Unauthorized: No auth token found. Please log in.');
  }

  for (let i = 0; i <= retries; i++) {
    try {
      // CRITICAL FIX: Use the stable API function
      const responseData = await _apiGenerateText(prompt, systemInstruction);
      
      // We expect the backend /api/ai/generate to return a JSON object with a 'response' field.
      if (responseData && responseData.response) {
        return responseData.response;
      }
            
      // Fallback if the response is valid HTTP but lacks the expected field
      throw new Error('No content returned from AI service, but call succeeded.');
    } catch (error) {
      console.warn(`AI attempt ${i + 1} failed:`, error.message);
            
      // Check for common auth errors propagated from the API client
      if (error.message.includes('Unauthorized') || String(error.message).includes('401')) { 
         throw new Error('Unauthorized. Please log in.');
      }
            
      if (i === retries) throw error;
      // Simple exponential backoff
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, i))); 
     }
  }
}

// --- EXPORTED FUNCTIONS ---
export async function generateJobDescriptionAI(title, department, skills) {
  const prompt = `Create a professional job description for "${title}" in "${department}". Skills: ${skills}. Use markdown headers.`;
  return callAI(prompt, 'You are an expert Technical Recruiter.');
}

export async function rewriteSocialPostAI(draft) {
  const prompt = `Rewrite this social post to be professional and engaging: "${draft}"`;
  return callAI(prompt, 'You are a Corporate Communications Expert.');
}

export async function chatWithHRPolicyAI(userQuery) {
  const systemPrompt = `You are "HiRo Assistant", a helpful HR AI. Answer general HR questions concisely. Redirect data requests to system commands.`;
  return callAI(userQuery, systemPrompt);
}

export async function generateAnalyticsSummaryAI(analyticsData) {
  const summaryPayload = JSON.stringify({
    trends: Array.isArray(analyticsData.lineData)
      ? analyticsData.lineData.slice(0, 5)
      : [],
    performance: Array.isArray(analyticsData.barData)
      ? analyticsData.barData.slice(0, 5)
      : [],
  });
  const prompt = `Analyze this HR data. Provide a short Executive Summary. Data: ${summaryPayload}`;
  return callAI(prompt, 'You are a CHRO Data Analyst.');
}

export async function generateTestScenarioAI() {
  const prompt = `Generate a complex natural language command for an HR AI system. Return ONLY the raw command string.`;
  return callAI(prompt, 'You are a QA Engineer.');
}

export async function generateSkillSuggestionsAI(role) {
  const prompt = `Based on the job role "${role}", suggest 5 key skills. Return as a comma-separated list.`;
  return callAI(prompt, 'You are a Career Development Coach.');
}

export async function refineFeedbackAI(draft) {
  const prompt = `Rewrite this feedback to be constructive and professional: "${draft}"`;
  return callAI(prompt, 'You are an HR Specialist.');
}
