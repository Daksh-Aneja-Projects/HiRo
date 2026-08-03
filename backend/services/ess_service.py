# backend/services/ess_service.py
"""Employee Self-Service (ESS) Agent: Handles all actions initiated by an individual employee.
Enforces strict data access scope (only own data) and uses the PII Vault for security."""
import asyncio 
import logging
from typing import Dict, Any, List, Optional 
from datetime import datetime, timezone
import uuid
from fastapi import HTTPException, status 

from config.settings import settings
from services.event_publisher_service import EventPublisherService 
from services.postgres_client import pg_client
from services import notification_service as notify_svc 
from services.pii_vault import PIIVault 
from services.enforcement_engine import runtime_enforcer 
from services.agent_spec_dsl import TriggerType 

logger = logging.getLogger(__name__)


def _as_date(value):
    """Coerce an ISO date string to a date object for asyncpg DATE columns."""
    if isinstance(value, str):
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    if isinstance(value, datetime):
        return value.date()
    return value


# --- Configuration Constants ---
ESS_AGENT_ID = "ESS_Service"
from services.pii_vault_core_logic_conceptual import POLICY_ESS_PURPOSE 

class ESSService:
    """
    Manages employee-initiated transactions and data retrieval."""
    
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        self.pii_vault = PIIVault.get_instance()
        logger.info(f"✓ {ESS_AGENT_ID} Initialized.")

    async def get_employee_dashboard_data(self, employee_id: str, requesting_agent_id: str) -> Dict[str, Any]:
        """
        Retrieves personalized data for the employee dashboard.
        Requires PII Vault for sensitive data (e.g., contact info, compensation)."""
        
        logger.info(f"Fetching dashboard data for {employee_id}.")
        
        # 1. Fetch PII Data (Securely via Vault)
        pii_query = "SELECT full_name_encrypted, email_encrypted FROM employee_pii WHERE employee_uuid = $1"
        try:
            # Signature: execute_pii_query(query, table_name, agent_id, auth=None, *query_args)
            sensitive_data = await self.pii_vault.execute_pii_query(
                pii_query, "employee_pii", requesting_agent_id,
                {"role": requesting_agent_id, "purpose": POLICY_ESS_PURPOSE},
                employee_id,
            )
        except PermissionError:
            sensitive_data = [{}] # Deny sensitive data but allow 
            logger.warning(f"PII access denied for {employee_id} to view sensitive data.")
            
        # 2. Fetch Non-PII Data (Directly via pg_client, though abstraction is better)
        non_pii_query = "SELECT balance_hours, used_hours FROM leave_balance WHERE employee_uuid = $1"
        general_data = await pg_client.fetch(non_pii_query, employee_id)

        # 3. Aggregate and sanitize output
        aggregated_data = general_data[0] if general_data else {}
        if sensitive_data:
            aggregated_data.update(sensitive_data[0])
            
        return {
            "status": "SUCCESS",
            "employee_id": employee_id,
            "data": aggregated_data,
            "dashboard_message": await self._dashboard_message(employee_id, aggregated_data),
        }

    async def _dashboard_message(self, employee_id: str, data: Dict[str, Any]) -> str:
        """A line about this person's actual position.

        This was the fixed string "Welcome back! Your compliance score is high.",
        shown to everyone regardless of anything, and referring to a score that
        was never looked up.
        """
        try:
            row = await pg_client.fetchrow(
                """SELECT
                     (SELECT COUNT(*) FROM leave_requests
                      WHERE employee_uuid = $1 AND status = 'PENDING') AS pending_leave,
                     (SELECT COUNT(*) FROM notifications
                      WHERE employee_uuid = $1 AND read_at IS NULL)    AS unread""",
                employee_id)
        except Exception:
            row = None

        pending = int((row or {}).get("pending_leave") or 0)
        unread = int((row or {}).get("unread") or 0)
        remaining = float(data.get("balance_hours") or 0)

        parts = []
        if unread:
            parts.append(f"{unread} unread update{'s' if unread != 1 else ''}")
        if pending:
            parts.append(f"{pending} request{'s' if pending != 1 else ''} waiting on a decision")
        if remaining > 0:
            parts.append(f"{remaining:g} hours of leave still available")

        if not parts:
            return "Welcome back. Nothing needs your attention right now."
        if len(parts) == 1:
            return f"Welcome back. You have {parts[0]}."
        return f"Welcome back. You have {', '.join(parts[:-1])}, and {parts[-1]}."

    async def submit_leave_request(self, employee_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits a new leave request and publishes an event for HR/Manager review."""
        request_id = f"LEAVE_{uuid.uuid4().hex[:8].upper()}"
        current_time = datetime.now(timezone.utc).isoformat()
        
        requested_hours = request_data.get('hours', 0) 
        
        # 1. Policy Enforcement Check (Pre-Execution for Leave Cap/Balance)
        policy_context = {
            "employee_id": employee_id,
            "Proposed": {
                "Hours": requested_hours,
                "StartDate": request_data['start_date'],
                "SubmittedDate": current_time
            },
            # NOTE: Full UDM context would typically be merged here if required by policy
            "UDM": {}
        }
        
        enforcer_result = await runtime_enforcer(
            TriggerType.LEAVE_REQUEST_SUBMIT.value, 
            policy_context
        )
        
        if enforcer_result["decision"] in ["DENY", "STOP", "BLOCK"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Leave request blocked by policy: {enforcer_result['reason']}"
            )

        # Ask for no more than is actually left. This counts what is already
        # awaiting a decision as well as what has been taken: without that, five
        # pending requests for the full balance would all be accepted, and the
        # manager would only find out by approving them one at a time.
        balance = await pg_client.fetchrow(
            """SELECT COALESCE(lb.balance_hours, 0) AS remaining,
                      COALESCE((SELECT SUM(hours) FROM leave_requests
                                WHERE employee_uuid = $1 AND status = 'PENDING'), 0) AS pending
               FROM leave_balance lb WHERE lb.employee_uuid = $1""",
            employee_id,
        )
        if balance is not None and requested_hours:
            available = float(balance["remaining"]) - float(balance["pending"])
            if float(requested_hours) > available:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(f"You asked for {float(requested_hours):g} hours but only "
                            f"{max(available, 0):g} are left, once the requests you already have "
                            "waiting for a decision are counted."),
                )

        async with pg_client.transaction(requesting_agent_id=ESS_AGENT_ID, purpose="submit_leave"):
            
            # 2. Insert the request into the UDM (transactional)
            insert_query = """
            INSERT INTO leave_requests (request_id, employee_uuid, start_date, end_date, hours, status, submitted_at)
            VALUES 
            ($1, $2, $3, $4, $5, $6, $7)
            """
            # start_date/end_date arrive as ISO strings but the columns are DATE,
            # and asyncpg requires real date objects.
            await pg_client.execute(
                insert_query,
                request_id,
                employee_id,
                _as_date(request_data['start_date']),
                _as_date(request_data['end_date']),
                requested_hours,
                "PENDING",
                current_time
            )
            
            # 3. Publish NATS event (The external action outside the DB)
            # publish_event(topic, payload, key) - the second parameter is `payload`.
            event_success = await self.publisher.publish_event(
                "HR.LEAVE_REQUEST_SUBMITTED",
                {
                    "request_id": request_id,
                    "employee_id": employee_id,
                    "requested_hours": requested_hours,
                    "status": "PENDING",
                    "submitted_at": current_time
                },
                key=employee_id
            )
            
            if not event_success:
                # If NATS fails, the transaction will automatically commit, but we should log/alert.
                logger.error(f"Failed to publish NATS event for leave request {request_id}. DB transaction committed.")
                
        await notify_svc.notify_manager_of(
            employee_id,
            notify_svc.KIND_APPROVAL_WAITING,
            "A time off request needs your decision",
            f"Someone on your team asked for {float(requested_hours or 0):g} hours off"
            f" from {request_data['start_date']}.",
            link="/manager-portal?module=approvals",
            related_id=request_id,
        )
        return {
            "status": "PENDING",
            "request_id": request_id,
            "message": "Leave request submitted and routed for manager approval."
        }