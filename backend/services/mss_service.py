import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from services.postgres_client import pg_client
from services.pii_vault import PIIVault
from services.event_publisher_service import EventPublisherService
from services import notification_service as notify_svc
import asyncio # CRITICAL FIX: Add missing import

logger = logging.getLogger(__name__)

class MSSService:
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        # CRITICAL FIX: Use the proper singleton getter
        self.pii_vault = PIIVault.get_instance()
        logger.info("✓ MSS Service Initialized.")

    async def get_manager_team_data(self, manager_id: str, requesting_agent_id: str,
                                    limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Retrieves and decrypts PII for the manager's direct reports.

        Paginated: decrypting an entire org's PII in one request is slow and
        floods the UI, so callers get a page plus the true total.
        """
        limit = max(1, min(int(limit or 50), 500))
        offset = max(0, int(offset or 0))
        query = (
            "SELECT employee_uuid, full_name_encrypted, email_encrypted "
            "FROM employee_pii WHERE manager_id = $1 ORDER BY employee_uuid LIMIT $2 OFFSET $3"
        )

        try:
            # Signature: execute_pii_query(query, table_name, agent_id, auth=None, *query_args)
            data = await self.pii_vault.execute_pii_query(
                query, "employee_pii", requesting_agent_id,
                {"role": requesting_agent_id}, manager_id, limit, offset,
            )
            total = 0
            try:
                row = await pg_client.fetchrow(
                    "SELECT COUNT(*) AS n FROM employee_pii WHERE manager_id = $1", manager_id
                )
                total = int((row or {}).get("n") or 0)
            except Exception:
                total = len(data)
            return {"manager": manager_id, "team": data, "total": total, "limit": limit, "offset": offset}
        except Exception as e:
            logger.error(f"PII query for manager {manager_id} failed: {e}")
            raise RuntimeError(f"Failed to retrieve team data securely: {e}")

    async def approve_leave(self, request_id: str, manager_id: str, approved: bool, comments: Optional[str] = None) -> Dict:
        """Approve or reject a leave request, and draw the hours off the balance.

        Approving used to update leave_requests and nothing else, so used_hours
        stayed at zero for every employee in the company however much leave was
        approved. Nothing ever drew the entitlement down, which meant the balance
        check on submission could never fire and people were approved far past
        what they had.

        The status update is conditional on the request still being PENDING, so
        approving twice cannot draw the balance down twice.
        """
        status = "APPROVED" if approved else "REJECTED"

        async with pg_client.transaction("MSS_Agent", "Leave_Approval") as conn:
            row = await conn.fetchrow(
                """UPDATE leave_requests
                   SET status=$1, approved_by=$2, decided_at=$3, denial_reason=$5
                   WHERE request_id=$4 AND status='PENDING'
                   RETURNING employee_uuid, hours""",
                status,
                manager_id,
                datetime.now(timezone.utc).isoformat(),
                request_id,
                comments if not approved else None,
            )

            if row is None:
                # Either the id is unknown or somebody has already decided it.
                existing = await conn.fetchrow(
                    "SELECT status FROM leave_requests WHERE request_id=$1", request_id)
                if existing is None:
                    raise ValueError(f"There is no leave request with the id {request_id}.")
                return {"status": existing["status"], "request_id": request_id,
                        "note": "This request had already been decided, so nothing changed."}

            if approved:
                await conn.execute(
                    """UPDATE leave_balance
                       SET used_hours = COALESCE(used_hours, 0) + $2,
                           balance_hours = GREATEST(COALESCE(balance_hours, 0) - $2, 0)
                       WHERE employee_uuid = $1""",
                    row["employee_uuid"], row["hours"],
                )

            await self.publisher.publish_event(
                "Employee_Action",
                {"type": "LEAVE_DECISION", "id": request_id, "status": status, "manager_id": manager_id, "timestamp": datetime.now(timezone.utc).isoformat()},
                key=request_id
            )

        # Tell the person who asked. Outside the transaction: a notification that
        # fails to send must not undo a decision that was made correctly.
        hours = float(row["hours"] or 0)
        await notify_svc.notify(
            row["employee_uuid"],
            notify_svc.KIND_LEAVE,
            f"Your time off was {'approved' if approved else 'declined'}",
            notify_svc.decision_sentence(
                f"request for {hours:g} hours of time off", approved,
                detail=(comments or "").strip()),
            link="/employee-portal?module=leave",
            related_id=request_id,
        )
        return {"status": status, "request_id": request_id}