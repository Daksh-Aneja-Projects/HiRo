# backend/services/internal_mock_api.py
"""
High-Fidelity Mock API for External Services (ERP/Regulatory Feed).

This module simulates the network latency and deterministic responses 
of the external services defined in the .env file (SAP, Oracle, Regulatory Feed).
It is used by ExternalAPIConnector as a fallback during local testing/development
when the real external URLs are not live.
"""
import time
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

# --- Configuration Constants (Matching expectations from agents) ---
MOCK_API_LATENCY_SECONDS = 0.05
MOCK_ERP_MIGRATION_STATUS = "SYNC_COMPLETE"

class InternalMockAPI:
    """Simulates API endpoints for external HRIS/Regulatory Feeds."""

    def __init__(self):
        logger.info("🎭 InternalMockAPI initialized for high-fidelity external service simulation.")

    def _simulate_network_delay(self):
        """Synchronous delay function that blocks."""
        time.sleep(MOCK_API_LATENCY_SECONDS)

    # --- REGULATORY FEED MOCK (Used by PolicyScrapingAgent via ExternalAPIConnector) ---
    def _regulatory_feed_updates_sync(self, jurisdiction: str) -> Dict[str, Any]:
        """Synchronous core logic."""
        self._simulate_network_delay()
        
        updates = []
        if jurisdiction in ["US-CA", "US"]:
            updates.append({
                "jurisdiction_code": jurisdiction,
                "policy_type": "MINIMUM_WAGE",
                "text": f"Effective 2027-01-01, the minimum hourly rate in {jurisdiction} shall not be less than $18.00 USD. This is a mandatory statutory requirement.",
                "effective_date": "2027-01-01"
            })
        if jurisdiction in ["EU", "FR", "DE"]:
             updates.append({
                "jurisdiction_code": jurisdiction,
                "policy_type": "DATA_PRIVACY",
                "text": f"All PII data processed for {jurisdiction} must comply with a zero-retention policy for non-active employees.",
                "effective_date": "2026-06-01"
            })
            
        return {"updates": updates}

    async def regulatory_feed_updates(self, jurisdiction: str) -> Dict[str, Any]:
        """Async wrapper for the blocking regulatory feed mock."""
        return await asyncio.to_thread(self._regulatory_feed_updates_sync, jurisdiction)


    # --- ERP INTEGRATION MOCK (Used by IntegrationAgent via ExternalAPIConnector) ---
    def _erp_config_sync_sync(self, erp_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous core logic."""
        self._simulate_network_delay()

        # Simulate processing the incoming payload
        processed_items = payload.get("num_config_items", 50)
        
        return {
            "migration_status": MOCK_ERP_MIGRATION_STATUS,
            "processed_items": processed_items,
            "system": erp_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def erp_config_sync(self, erp_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Async wrapper for the blocking ERP mock."""
        return await asyncio.to_thread(self._erp_config_sync_sync, erp_type, payload)


# Global instance
internal_mock_api = InternalMockAPI()