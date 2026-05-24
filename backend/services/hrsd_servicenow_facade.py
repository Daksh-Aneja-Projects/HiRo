# /backend/services/hrsd_servicenow_facade.py
"""HRSD ServiceNow Facade: Manages synchronous, idempotent interaction with an external ITSM system (ServiceNow). Used to synchronize ticket status and notes."""
import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx
from datetime import datetime, timezone
import uuid
import json
from config.settings import settings
from services.external_api_connector import ExternalAPIConnector
from services.postgres_client import pg_client
try:
    import psycopg2
except ImportError:
    psycopg2 = None 

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
FACADE_AGENT_ID = "ServiceNowFacadeAgent"
SNOW_URL = settings.SNOW_API_URL
SNOW_MOCK_TABLE = "sn_hr_ticket_map"

class HRSDServiceNowFacade:
    """
    Provides idempotent and transactional functions for ServiceNow integration.
    """
    def __init__(self, api_connector: ExternalAPIConnector):
        self.api_connector = api_connector
        # CRITICAL FIX 1: REMOVED asyncio.create_task here.
        # Task creation must be deferred.
        logger.info(f"✓ {FACADE_AGENT_ID} Initialized (ServiceNow Facade Active).")

    async def _ensure_mapping_table_exists(self):
        """
        Runs the DDL to create the ServiceNow mapping table in a dedicated thread.
        """
        def run_ddl_sync():
            if not psycopg2:
                logger.error("psycopg2 not available. Cannot ensure ServiceNow mapping table DDL.")
                return
                
            conn = None
            db_url = settings.postgres_url()
            try:
                # CRITICAL FIX: psycopg2.connect requires the DSN URL, which is available via settings.postgres_url()
                conn = psycopg2.connect(db_url)
                conn.autocommit = True
                cur = conn.cursor()
                
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {SNOW_MOCK_TABLE} (
                        hiro_id VARCHAR(50) PRIMARY KEY,
                        snow_id VARCHAR(50) NOT NULL,
                        snow_number VARCHAR(50),
                        sync_status VARCHAR(50) NOT NULL,
                        last_sync_at TIMESTAMP WITH TIME ZONE
                    );
                """)
                logger.info(f"✅ Ensured {SNOW_MOCK_TABLE} table exists.")
            except Exception as e:
                # CRITICAL FIX 3: Safely ignore the PostgreSQL type creation error 
                error_msg = str(e)
                if "duplicate key value violates unique constraint" in error_msg and "pg_type_typname_nsp_index" in error_msg:
                    logger.warning(f"⚠️ DDL Warning: Ignoring duplicate type creation error for {SNOW_MOCK_TABLE}. Table likely exists.")
                else:
                    logger.error(f"❌ Failed to create {SNOW_MOCK_TABLE} DDL: {e}")
            finally:
                if conn: conn.close()
        
        # CRITICAL FIX 2: Added conditional check for psycopg2 before asyncio.to_thread
        if psycopg2:
            await asyncio.to_thread(run_ddl_sync)
        else:
            logger.warning("Skipping DDL setup for ServiceNow facade due to missing psycopg2.")

    async def _get_snow_id_and_sync_status(self, hiro_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the external ServiceNow ID and current sync status from the internal mapping table.
        """
        query = f"SELECT snow_id, sync_status, last_sync_at FROM {SNOW_MOCK_TABLE} WHERE hiro_id = $1"
        try:
            results = await pg_client.fetch(query, hiro_id)
            return results[0] if results else None
        except Exception as e:
            if "relation" in str(e) and "does not exist" in str(e):
                logger.warning(f"DB Warning: {SNOW_MOCK_TABLE} does not exist during lookup.")
                return None
            # CRITICAL FIX: Propagate other unexpected errors
            raise

    async def create_external_ticket(self, hiro_ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new ticket in ServiceNow or updates an existing one if already mapped (idempotency).
        """
        hiro_id = hiro_ticket_data['ticket_id']
        mapping = await self._get_snow_id_and_sync_status(hiro_id)
        
        if mapping and mapping.get('snow_id'):
            logger.info(f"Ticket {hiro_id} already mapped to SNOW ID {mapping['snow_id']}. Skipping creation.")
            return {"status": "SKIPPED_IDEMPOTENT", "snow_id": mapping['snow_id']}
            
        snow_payload = {
            "short_description": hiro_ticket_data.get('title', 'No Title'), # CRITICAL FIX: Use 'title' not 'subject' based on HRSDTicket model
            "description": hiro_ticket_data['description'],
            "u_hiro_id": hiro_id,
            "priority": "3" # Mock Priority
        }
        
        try:
            # NOTE: Assuming api_connector._request_with_retry handles Auth/Headers based on settings
            response = await self.api_connector._request_with_retry(
                method="POST",
                url=f"{SNOW_URL}/api/now/table/incident",
                system_id="SERVICENOW_API",
                json=snow_payload
            )
            
            snow_response = response.json().get('result', {})
            snow_id = snow_response.get('sys_id')
            incident_number = snow_response.get('number')
            
            if not snow_id:
                raise RuntimeError(f"ServiceNow creation failed to return sys_id. Response: {response.text}")
        except Exception as e:
            logger.error(f"ServiceNow API call failed for {hiro_id}: {e}")
            raise RuntimeError(f"ServiceNow integration failed: {e}")

        async with pg_client.transaction(requesting_agent_id=FACADE_AGENT_ID, purpose="snow_map"):
            insert_query = f"""
            INSERT INTO {SNOW_MOCK_TABLE} (hiro_id, snow_id, snow_number, sync_status, last_sync_at)
            VALUES ($1, $2, $3, $4, $5)
            """
            await pg_client.execute(insert_query, hiro_id, snow_id, incident_number, "MAPPED", datetime.now(timezone.utc).isoformat())

        return {
            "status": "CREATED_MAPPED",
            "snow_id": snow_id,
            "incident_number": incident_number,
        }

    async def synchronize_status_update(self, hiro_id: str, new_status: str, comments: str) -> bool:
        """
        Updates the status and adds comments to the corresponding ServiceNow ticket.
        """
        mapping = await self._get_snow_id_and_sync_status(hiro_id)
        if not mapping or not mapping.get('snow_id'):
            logger.warning(f"Cannot sync {hiro_id}: No ServiceNow ID mapping found.")
            return False
            
        snow_id = mapping['snow_id']
        
        # Map HiRo status (TicketStatus Enum values) to SNOW state codes
        snow_state_map = {"RESOLVED_BY_AGENT": "3", "OPEN": "1", "IN_PROGRESS": "2", "CLOSED": "7", "NEW": "1", "IN_TRIAGE": "2", "RESOLUTION": "2", "COMPLIANCE_REVIEW": "2", "REJECTED": "7"}
        snow_state = snow_state_map.get(new_status, "7")
        
        update_payload = {
            "state": snow_state,
            "work_notes": f"HiRo Update [{new_status}]: {comments}"
        }
        
        try:
            await self.api_connector._request_with_retry(
                method="PUT",
                url=f"{SNOW_URL}/api/now/table/incident/{snow_id}", 
                system_id="SERVICENOW_API",
                json=update_payload
            )
            
            async with pg_client.transaction(requesting_agent_id=FACADE_AGENT_ID, purpose="snow_sync"):
                update_query = f"UPDATE {SNOW_MOCK_TABLE} SET sync_status = $1, last_sync_at = $2 WHERE hiro_id = $3"
                await pg_client.execute(update_query, new_status, datetime.now(timezone.utc).isoformat(), hiro_id)
                
            logger.info(f"Synced ticket {hiro_id} to ServiceNow ID {snow_id} with status {new_status}.")
            return True
        except Exception as e:
            logger.error(f"ServiceNow sync failed for {hiro_id}: {e}")
            return False
