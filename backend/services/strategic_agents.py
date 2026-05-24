# /backend/services/strategic_agents.py - FIXED
# services/strategic_agents.py
"""Strategic Agents: Deterministic Business Logic."""
import logging
from typing import Dict, Any, List # CRITICAL FIX: Add missing imports
from datetime import datetime, timezone # CRITICAL FIX: Add missing imports
import uuid # CRITICAL FIX: Add missing imports
import re
import asyncio
from services.ai_services import AIService

logger = logging.getLogger(__name__)

# --- AGENT 8: EFRA (Synchronous Logic - must be run via to_thread) ---
class EFRAgent:
    # CRITICAL FIX: Make this method async as it calls potentially async functions 
    # (like pub/sub after synthesis, though not shown) and for consistency.
    async def synthesize_journal_entry(self, event_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesizes GL entry."""
        if event_type == "Comp.Change.Submit":
            try:
                amount = float(context.get('amount', 0))
                if amount <= 0: 
                    return {"status": "SKIPPED", "reason": "Amount is zero or negative."}
                
                # CRITICAL FIX: Wrap blocking uuid generation in asyncio.to_thread
                entry_id = await asyncio.to_thread(lambda: f"JE_{uuid.uuid4().hex[:6]}")
                
                return {
                    "entry_id": entry_id,
                    "debits": [{"account": "6000-Salaries", "amount": amount}],
                    "credits": [{"account": "2000-Accrual", "amount": amount}],
                    "status": "RECONCILED"
                }
                
            except ValueError:
                return {"status": "ERROR", "reason": "Invalid amount format."}
                
        return {"status": "SKIPPED"}

# --- AGENT 9: DCA (Synchronous Logic - must be run via to_thread) ---
class DCAgent:
    # CRITICAL FIX: Make this method async for consistency and thread-safety
    async def forecast_liquidity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates 90-day cash position."""
        try:
            cash = float(data.get('cash', 1000000))
            receivables = float(data.get('receivables', 500000))
            burn_rate = float(data.get('monthly_burn', 200000))
        except ValueError:
            return {"status": "ERROR", "message": "Invalid numeric input for financial data."}
            
        projected = cash + (receivables * 0.9) - (burn_rate * 3)
        
        return {
            "current_cash": cash,
            "projected_90_day": projected,
            "status": "HEALTHY" if projected > 500000 else "CRITICAL"
        }

# --- AGENT 26: CIA (Async AI) ---
class CIAgent:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def identify_market_vulnerabilities(self, segment: str) -> Dict[str, Any]:
        """Uses generic AI Service to analyze market."""
        prompt = f"Analyze {segment} talent market.\nIdentify 1 weakness, 1 opportunity. Return JSON."
        try:
            insight = await self.ai_service.generate_json_response(
                prompt, 
                response_schema={"type": "object", "properties": {"weakness": {"type": "string"}, "opportunity": {"type": "string"}}}
            )
            return {"segment": segment, "analysis": insight}
            
        except Exception as e:
            logger.error(f"CIAgent AI analysis failed: {e}")
            return {"segment": segment, "analysis": {"weakness": "AI service unavailable or unresponsive."}}

# --- AGENT 27: GTMF (Synchronous Logic - must be run via to_thread) ---
class GTMFabric:
    def synthesize_market_data(self, job_title: str) -> Dict[str, Any]:
        """Calculates comp band based on title length (Deterministic Hash)."""
        seed = sum(ord(c) for c in 
        job_title)
        base = 80000 + (seed * 100)
        return {
            "title": job_title,
            "median": base,
            "range": [round(base * 0.8, 2), round(base * 1.2, 2)]
        }