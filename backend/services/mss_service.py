import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from services.postgres_client import pg_client
from services.pii_vault import PIIVault
from services.event_publisher_service import EventPublisherService
import asyncio # CRITICAL FIX: Add missing import

logger = logging.getLogger(__name__)

class MSSService:
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        # CRITICAL FIX: Use the proper singleton getter
        self.pii_vault = PIIVault.get_instance()
        logger.info("✓ MSS Service Initialized.")

    async def get_manager_team_data(self, manager_id: str, requesting_agent_id: str) -> Dict[str, Any]:
        """Retrieves and decrypts PII for the manager's direct reports."""
        query = "SELECT employee_uuid, full_name_encrypted, email_encrypted FROM employee_pii WHERE manager_id = $1"
        
        try:
            # Signature: execute_pii_query(query, table_name, agent_id, auth=None, *query_args)
            data = await self.pii_vault.execute_pii_query(
                query, "employee_pii", requesting_agent_id,
                {"role": requesting_agent_id}, manager_id,
            )
            return {"manager": manager_id, "team": data}
        except Exception as e:
            logger.error(f"PII query for manager {manager_id} failed: {e}")
            raise RuntimeError(f"Failed to retrieve team data securely: {e}")

    async def approve_leave(self, request_id: str, manager_id: str, approved: bool, comments: Optional[str] = None) -> Dict:
        """Approves or rejects a leave request with transactional safety."""
        status = "APPROVED" if approved else "REJECTED"

        async with pg_client.transaction("MSS_Agent", "Leave_Approval") as conn:
            # CRITICAL FIX: Use the transaction connection object for execution
            await conn.execute(
                "UPDATE leave_requests SET status=$1, approved_by=$2, decided_at=$3, denial_reason=$5 WHERE request_id=$4",
                status,
                manager_id,
                datetime.now(timezone.utc).isoformat(),
                request_id,
                comments if not approved else None
            )

            await self.publisher.publish_event(
                "Employee_Action",
                {"type": "LEAVE_DECISION", "id": request_id, "status": status, "manager_id": manager_id, "timestamp": datetime.now(timezone.utc).isoformat()},
                key=request_id
            )

            return {"status": status, "request_id": request_id}