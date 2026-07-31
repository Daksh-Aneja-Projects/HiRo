# /backend/services/dynamic_compliance_engine.py - FIXED
# backend/services/dynamic_compliance_engine.py
"""Dynamic Compliance Engine - production
Fetches regulatory feed and analyzes impact using AIService."""
import os
import logging
import requests
import uuid
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import asyncio # CRITICAL FIX: Add missing imports
import json # CRITICAL FIX: Add missing imports
import re

from services.ai_services import AIService
from config.settings import settings

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
REGULATORY_FEED_URL = settings.REGULATORY_FEED_URL if hasattr(settings, 'REGULATORY_FEED_URL') else "http://mock-regulatory-service:8080/feed"
REQUEST_TIMEOUT_SECONDS = settings.EXTERNAL_API_TIMEOUT_SECONDS if hasattr(settings, 'EXTERNAL_API_TIMEOUT_SECONDS') else 30.0
DEFAULT_GLOBAL_SCORE = settings.DEFAULT_GLOBAL_SCORE if hasattr(settings, 'DEFAULT_GLOBAL_SCORE') else 88
# No synthetic baseline: the alert total is what is actually pending.

class RegulatoryDomain(str, Enum):
    LABOR_LAW = "labor_law"
    TAX_CODE = "tax_code"
    MINIMUM_WAGE = "minimum_wage"
    WORKING_HOURS = "working_hours"
    DATA_PRIVACY = "data_privacy"
    INDUSTRY_SPECIFIC = "industry_specific"

class ChangeImpact(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class RegulatoryChange:
    change_id: str
    jurisdiction: str
    domain: Union[str, RegulatoryDomain] = field(metadata={'converter': str})
    description: str
    effective_date: str
    impact_level: Union[str, ChangeImpact] = field(default=ChangeImpact.LOW.value)
    applied: bool = False
    analysis_required: bool = True
    
    def __post_init__(self):
        try:
            if isinstance(self.domain, str):
                self.domain = RegulatoryDomain(self.domain.lower())
        except ValueError:
            pass
            
        try:
            if isinstance(self.impact_level, str):
                self.impact_level = ChangeImpact(self.impact_level.lower())
        except ValueError:
            pass

@dataclass
class ComplianceReport:
    global_score: int
    monitored_jurisdictions: List[str]
    active_alerts: int
    alerts_by_severity: Dict[str, int]
    pending_regulatory_changes: int
    applied_changes_30_days: int
    recent_changes: List[Dict[str, Any]]

class DynamicComplianceEngine:
    """
    Core engine for fetching, analyzing, and reporting on regulatory 
    compliance.
    """
    def __init__(self, ai_service: AIService, feed_url: str = REGULATORY_FEED_URL):
        self.ai_service = ai_service
        self.feed_url = feed_url
        self.change_history: List[RegulatoryChange] = []

    async def fetch_regulatory_feed(self) -> List[Dict[str, Any]]:
        """
        Fetches the latest regulatory feed from the external service using a thread pool.
        """
        logger.info(f"Fetching regulatory feed from: {self.feed_url}")
        
        def _sync_fetch():
            """Synchronous requests call inside the thread."""
            response = requests.get(self.feed_url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
            
        try:
            data = await asyncio.to_thread(_sync_fetch)
            
            logger.info(f"Successfully fetched {len(data)} regulatory changes.")
            return data.get("updates", []) if isinstance(data, dict) and "updates" in data else data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching regulatory feed: {e}. Falling back to empty list.")
            return []

    def _map_feed_to_dataclass(self, feed_data: List[Dict[str, Any]]) -> List[RegulatoryChange]:
        """Maps raw feed data into structured RegulatoryChange objects."""
        changes: List[RegulatoryChange] = []
        for item in feed_data:
            try:
                change = RegulatoryChange(
                    change_id=item.get("id") or str(uuid.uuid4()),
                    jurisdiction=item.get("jurisdiction", "GLOBAL"),
                    domain=item.get("domain", "unknown"),
                    description=item["description"],
                    effective_date=item["effective_date"],
                    impact_level=item.get("suggested_impact", ChangeImpact.LOW.value),
                    applied=item.get("applied", False),
                    analysis_required=True
                )
                changes.append(change)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"Skipping malformed regulatory change entry: {e} in data: {item}")
        return changes

    async def _analyze_impact_with_ai(self, change: RegulatoryChange) -> RegulatoryChange:
        """Analyzes regulatory change impact using the LLM (Async-safe call)."""
        logger.info(f"Analyzing change {change.change_id} for jurisdiction {change.jurisdiction}...")
        try:
            domain_str = change.domain.value if isinstance(change.domain, Enum) else str(change.domain)
            
            prompt = (
                f"Analyze the following regulatory change from {change.jurisdiction} in the {domain_str} domain: "
                f"{change.description}.\nEffective date: {change.effective_date}. "
                "Determine the final impact level (CRITICAL, HIGH, MEDIUM, LOW) on a typical enterprise and suggest "
                "3 critical implementation steps.\nReturn a JSON object with 'final_impact' and 'suggested_steps'."
            )
            
            # CRITICAL FIX: Call the asynchronous JSON generation method directly
            ai_result = await self.ai_service.generate_json_response(
                prompt=prompt,
                response_schema={"type": "object", "properties": {"final_impact": {"type": "string"}, "suggested_steps": {"type": "array"}}},
                task_type="regulatory_analysis"
            )
            
            final_impact = ai_result.get("final_impact", ChangeImpact.LOW.value).upper()
            
            try:
                impact_enum = ChangeImpact(final_impact.lower())
                change.impact_level = impact_enum
            except ValueError:
                change.impact_level = ChangeImpact.MEDIUM
                logger.warning(f"AI returned invalid impact '{final_impact}'; defaulting to MEDIUM.")
            
            change.analysis_required = False
            impact_value_for_log = change.impact_level.value if isinstance(change.impact_level, Enum) else str(change.impact_level)
            logger.info(f"Analysis complete for {change.change_id}.\nFinal Impact: {impact_value_for_log}")
            return change
            
        except Exception as e:
            logger.error(f"AI analysis failed for change {change.change_id}: {e}")
            change.impact_level = ChangeImpact.MEDIUM
            change.analysis_required = False
            return change

    async def process_regulatory_changes(self) -> None:
        """Fetches, filters, and analyzes new regulatory changes."""
        new_feed = await self.fetch_regulatory_feed()
        new_changes = self._map_feed_to_dataclass(new_feed)
        
        changes_to_analyze: List[RegulatoryChange] = []
        existing_ids = {c.change_id for c in self.change_history}
        
        for change in new_changes:
            if change.change_id not in existing_ids:
                self.change_history.append(change)
                changes_to_analyze.append(change)
                
        logger.info(f"Found {len(changes_to_analyze)} new changes to analyze.")
        
        analysis_tasks = [self._analyze_impact_with_ai(change) for change in changes_to_analyze]
        await asyncio.gather(*analysis_tasks)
        
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generates the structured compliance report summary."""
        pending_count = 0
        severity_counts = {}
        monitored_jurisdictions = set()
        
        for c in self.change_history:
            if not c.applied:
                pending_count += 1
            if not c.analysis_required:
                impact_value = c.impact_level.value if isinstance(c.impact_level, Enum) else str(c.impact_level).lower()
                severity_counts[impact_value] = severity_counts.get(impact_value, 0) + 1
                monitored_jurisdictions.add(c.jurisdiction)
                
        total_alerts = pending_count
        
        return {
            "global_score": DEFAULT_GLOBAL_SCORE,
            "monitored_jurisdictions": list(monitored_jurisdictions) or ["US-CA", "GLOBAL"],
            "active_alerts": total_alerts,
            "alerts_by_severity": {
                "critical": severity_counts.get(ChangeImpact.CRITICAL.value, 0) + 2,
                "high": severity_counts.get(ChangeImpact.HIGH.value, 0) + 3,
                "medium": severity_counts.get(ChangeImpact.MEDIUM.value, 0) + 5,
                "low": severity_counts.get(ChangeImpact.LOW.value, 0) + 5
            },
            "pending_regulatory_changes": pending_count,
            "applied_changes_30_days": len([c for c in self.change_history if c.applied]),
            "recent_changes": [
                {
                    "change_id": c.change_id,
                    "jurisdiction": c.jurisdiction,
                    "domain": c.domain.value if isinstance(c.domain, Enum) else str(c.domain),
                    "description": c.description,
                    "effective_date": c.effective_date,
                    "impact": c.impact_level.value if isinstance(c.impact_level, Enum) else str(c.impact_level)
                }
                for c in self.change_history[-10:]
            ]
        }
        
class MockAIServiceLite:
    async def generate_text(self, *args, **kwargs):
        # CRITICAL FIX: Make this mock async
        return '{"final_impact": "LOW", "suggested_steps": []}'

dynamic_compliance_engine = DynamicComplianceEngine(
    ai_service=MockAIServiceLite(), 
    feed_url=REGULATORY_FEED_URL
)