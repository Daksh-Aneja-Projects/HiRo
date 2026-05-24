# /backend/services/privacy_consent_management_agent.py - FIXED
# /C:/HiRo Project/backend/services/privacy_consent_management_agent.py
"""Privacy Consent Agent: DB-Backed Consent Verification."""
import logging
from typing import Dict, Any, Optional # CRITICAL FIX: Add missing imports
from services.postgres_client import pg_client
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class PrivacyConsentManagementAgent:
    def __init__(self):
        logger.info("✓ PrivacyConsentManagementAgent Initialized (DB Mode).")

    async def get_consent_status(self, employee_id: str, purpose_id: str) -> bool:
        """Retrieves consent from Postgres."""
        query = """
            SELECT has_consent FROM privacy_consents
            WHERE employee_id = $1 AND 
            purpose_id = $2
        """
        row = await pg_client.fetchrow(query, employee_id, purpose_id)
        # Default to FALSE (Opt-in model) if no record found
        return row['has_consent'] if row and 'has_consent' in row else False

    async def check_data_access_policy(self,                   
                                       employee_id: str,
                                       data_field: str,
                                       usage_purpose: str,
                                       requesting_agent_id: str) -> bool:
        """Verifies access authorization."""
        
        # 1. Audit Override check
        if usage_purpose == "legal_audit" and requesting_agent_id == "AuditAgent":
            return True
        
        # 2. Database Consent Check
        has_consent = await self.get_consent_status(employee_id, usage_purpose)
        if not has_consent:
            logger.warning(f"⛔ ACCESS DENIED: {requesting_agent_id} -> {data_field} (User {employee_id} denied {usage_purpose})")
            return False
            
        logger.info(f"🔓 ACCESS GRANTED: {requesting_agent_id} -> {data_field}")
        return True

    async def update_consent(self, employee_id: str, purpose_id: str, status: bool) -> bool:
        """Upserts consent record."""
        query = """
            INSERT INTO privacy_consents (employee_id, purpose_id, has_consent, updated_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (employee_id, purpose_id) 
            DO UPDATE SET has_consent = $3, updated_at = $4
        """
        await pg_client.execute(query, employee_id, purpose_id, status, datetime.now(timezone.utc).isoformat())
        logger.info(f"Consent updated: {employee_id} [{purpose_id}] = {status}")
        return True
