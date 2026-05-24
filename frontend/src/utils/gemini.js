// frontend/src/utils/gemini.js - FINAL STABILIZATION
// Purpose: Backward compatibility layer, mapping old function names to the new unified ai_client.
import { 
    generateJobDescriptionAI as genJob, 
    rewriteSocialPostAI as rewritePost, 
    chatWithHRPolicyAI as chatAI, 
    generateAnalyticsSummaryAI as genAnalytics, 
    generateTestScenarioAI as genTest, 
    generateSkillSuggestionsAI as genSkills, 
    refineFeedbackAI as refineFeedback 
} from './ai_client'; 

// Ensure all exports are mapped correctly and explicitly to maintain functionality
export const generateJobDescriptionAI = genJob;
export const rewriteSocialPostAI = rewritePost;
export const chatWithHRPolicyAI = chatAI;
export const generateAnalyticsSummaryAI = genAnalytics;
export const generateTestScenarioAI = genTest;
export const generateSkillSuggestionsAI = genSkills;
export const refineFeedbackAI = refineFeedback;