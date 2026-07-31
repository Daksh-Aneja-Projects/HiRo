# /backend/services/multi_agent_hrsd.py - FIXED (Agent Serialization)
"""Multi-Agent HRSD System: Handles employee tickets with Postgres persistence."""
import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone # CRITICAL FIX: Ensure timezone is imported
import uuid
from config.settings import settings
from services.ai_services import AIService 
from services.event_publisher_service import EventPublisherService
from services.hr_modules import HRModulesService 
from services.schemas.models import HRSDTicket, TicketStatus, TicketPriority # CRITICAL FIX: Ensure models are imported
from services.postgres_client import pg_client

logger = logging.getLogger(__name__)

HRSD_DB_TABLE = "hrsd_tickets" 
TICKET_QUEUE_TOPIC = getattr(settings, 'TICKET_QUEUE_TOPIC', "hcm.tickets.inbound")

class HRSDSubAgent(str):
    PAYROLL = "PayrollAgent"
    BENEFITS = "BenefitsAgent"
    TIME_OFF = "TimeOffAgent"
    IT_SUPPORT = "ITSupportAgent"
    PROJECT_FOLLOWUP = "ProjectFollowupAgent" 
    TRIAGE = "TriageAgent"

class MultiAgentHRSDSystem:
    def __init__(self, ai_service: AIService, hr_modules_service: HRModulesService, publisher: EventPublisherService):
        self.ai_service = ai_service 
        self.hr_modules = hr_modules_service
        self.publisher = publisher
        logger.info("✓ Multi-Agent HRSD System Initialized (Postgres persistence assumed).")

    # The hrsd_tickets table has no columns for employee_id / resolution_summary /
    # resolved_at, so those model-only fields live in the metadata JSONB.
    OPEN_STATUSES = ["NEW", "IN_TRIAGE", "IN_RESOLUTION", "COMPLIANCE_REVIEW"]

    @staticmethod
    def _safe_enum(enum_cls, value, default):
        try:
            return enum_cls(value)
        except (ValueError, KeyError):
            return default

    def _row_to_ticket(self, row: Dict[str, Any]) -> HRSDTicket:
        row = dict(row)
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (ValueError, TypeError):
                meta = {}
        resolved_at = meta.get("resolved_at")
        if isinstance(resolved_at, str):
            try:
                resolved_at = datetime.fromisoformat(resolved_at)
            except ValueError:
                resolved_at = None
        return HRSDTicket(
            ticket_id=row["ticket_id"],
            employee_id=meta.get("employee_id") or "UNKNOWN",
            title=row.get("subject") or "(no subject)",
            description=row.get("description") or "",
            status=self._safe_enum(TicketStatus, row.get("status"), TicketStatus.NEW),
            priority=self._safe_enum(TicketPriority, row.get("priority"), TicketPriority.MEDIUM),
            assigned_agent=row.get("assigned_agent"),
            created_at=row.get("created_at") or datetime.now(timezone.utc),
            resolution_summary=meta.get("resolution_summary"),
            resolved_at=resolved_at,
        )

    async def _save_ticket(self, ticket: HRSDTicket):
        """UPSERT the ticket into Postgres (model-only fields go to metadata JSONB)."""
        meta = {
            "employee_id": ticket.employee_id,
            "resolution_summary": ticket.resolution_summary,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        }
        await pg_client.execute(
            f"""
            INSERT INTO {HRSD_DB_TABLE}
                (ticket_id, created_at, status, assigned_agent, priority, subject, description, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            ON CONFLICT (ticket_id) DO UPDATE SET
                status = EXCLUDED.status,
                assigned_agent = EXCLUDED.assigned_agent,
                priority = EXCLUDED.priority,
                subject = EXCLUDED.subject,
                description = EXCLUDED.description,
                metadata = EXCLUDED.metadata
            """,
            ticket.ticket_id,
            ticket.created_at,
            ticket.status.value,
            ticket.assigned_agent,
            ticket.priority.value,
            ticket.title,
            ticket.description,
            json.dumps(meta),
        )
        logger.info(f"Saved HRSD ticket {ticket.ticket_id} to Postgres.")

    async def _get_ticket(self, ticket_id: str) -> Optional[HRSDTicket]:
        row = await pg_client.fetchrow(
            f"SELECT * FROM {HRSD_DB_TABLE} WHERE ticket_id = $1", ticket_id
        )
        return self._row_to_ticket(row) if row else None

    async def list_tickets(self, employee_id: Optional[str] = None,
                           limit: Optional[int] = None, offset: Optional[int] = None) -> Dict[str, Any]:
        """Return recent tickets, optionally filtered by employee_id."""
        limit = min(int(limit or 50), 200)
        offset = max(int(offset or 0), 0)
        if employee_id:
            rows = await pg_client.fetch(
                f"SELECT * FROM {HRSD_DB_TABLE} WHERE metadata->>'employee_id' = $1 "
                f"ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                employee_id, limit, offset,
            )
        else:
            rows = await pg_client.fetch(
                f"SELECT * FROM {HRSD_DB_TABLE} ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
        tickets = [self._row_to_ticket(r).model_dump(mode="json") for r in rows]
        return {"tickets": tickets, "count": len(tickets)}

    async def get_overview(self, sla_hours: Optional[int] = None) -> Dict[str, Any]:
        """Real HRSD monitoring counts: active tickets, SLA breaches, by-status breakdown."""
        sla_hours = int(sla_hours or getattr(settings, "HRSD_SLA_HOURS", 24))
        rows = await pg_client.fetch(
            f"SELECT status, COUNT(*) AS c FROM {HRSD_DB_TABLE} GROUP BY status"
        )
        by_status = {r["status"]: r["c"] for r in rows}
        active = sum(c for s, c in by_status.items() if s in self.OPEN_STATUSES)
        breach = await pg_client.fetchrow(
            f"SELECT COUNT(*) AS c FROM {HRSD_DB_TABLE} "
            f"WHERE status = ANY($1::text[]) AND created_at < now() - make_interval(hours => $2)",
            self.OPEN_STATUSES, sla_hours,
        )
        return {
            "active_tickets": active,
            "sla_breaches": (breach["c"] if breach else 0),
            "tickets_by_status": by_status,
            "total_tickets": sum(by_status.values()),
            # This was the literal "Online", so a dead triage model still read as
            # healthy. It now reflects whether classification can actually run.
            "agent_status": "Online" if await self._triage_available() else "Degraded",
        }

    async def _triage_available(self) -> bool:
        """Whether the model that classifies incoming cases can be reached."""
        try:
            models = await self.ai_service.get_ai_models()
            return bool(models)
        except Exception:
            return False

    async def _classify(self, ticket: HRSDTicket) -> Dict[str, Any]:
        """Ask the local model what this ticket is about and how urgent it is.

        If the model is unreachable the ticket stays where a person will see it,
        at its submitted priority, rather than being given a confident-looking
        category nobody computed.
        """
        schema = {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": list(self._ROUTES.keys())},
                "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "summary": {"type": "string"},
            },
            "required": ["category", "priority", "summary"],
        }
        prompt = (
            "Read this HR service request and classify it.\n\n"
            f"Subject: {ticket.title}\n"
            f"Description: {ticket.description}\n\n"
            f"category must be one of: {', '.join(self._ROUTES)}.\n"
            "priority: CRITICAL only if someone cannot be paid or cannot work at all; "
            "HIGH if it affects pay, benefits or access this week; MEDIUM by default; "
            "LOW for questions with no deadline.\n"
            "summary: one sentence a support agent can read at a glance."
        )
        try:
            result = await self.ai_service.generate_json_response(prompt, schema, task_type="hrsd_triage")
        except Exception as e:
            logger.warning(f"Triage model unavailable for {ticket.ticket_id}: {e}")
            result = {}

        category = str(result.get("category") or "").lower()
        if category not in self._ROUTES:
            return {
                "new_status": TicketStatus.NEW.value,
                "new_priority": ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
                "next_agent": HRSDSubAgent.TRIAGE,
                "summary": "This could not be classified automatically, so a person needs to look at it.",
                "classified": False,
            }

        priority = str(result.get("priority") or "MEDIUM").upper()
        if priority not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            priority = "MEDIUM"
        return {
            "new_status": TicketStatus.TRIAGE.value,
            "new_priority": priority,
            "next_agent": self._ROUTES[category],
            "summary": str(result.get("summary") or "").strip() or ticket.title,
            "classified": True,
        }

    async def create_ticket(self, employee_id: str, subject: str, description: str) -> HRSDTicket:
        new_ticket = HRSDTicket(
            ticket_id=f"T-{uuid.uuid4().hex[:8].upper()}",
            employee_id=employee_id,
            title=subject,
            description=description,
            status=TicketStatus.NEW,
            priority=TicketPriority.MEDIUM,
            created_at=datetime.now(timezone.utc)
        )
        await self._save_ticket(new_ticket)
        
        # CRITICAL FIX: Publish the NEW TICKET event
        await self.publisher.publish_agent_task(
            task_data=new_ticket.model_dump(mode='json'),
            topic="HRSD_NEW_TICKET",
            key=new_ticket.ticket_id
        )
        return new_ticket

    # Which specialist handles what. The model picks one of these keys; anything
    # it invents falls back to human triage rather than being routed at random.
    _ROUTES = {
        "payroll": HRSDSubAgent.PAYROLL,
        "benefits": HRSDSubAgent.BENEFITS,
        "time_off": HRSDSubAgent.TIME_OFF,
        "it_support": HRSDSubAgent.IT_SUPPORT,
        "other": HRSDSubAgent.TRIAGE,
    }

    async def triage_ticket(self, ticket_id: str) -> HRSDTicket:
        """Read the ticket and route it to the right specialist.

        This used to be a fixed dict: every ticket, whatever it said, came out as
        a HIGH priority IT access issue. A payroll complaint was routed to IT
        support. `self.ai_service` was assigned in the constructor and never read.
        """
        ticket = await self._get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")

        triage_data = await self._classify(ticket)

        # 2. Update ticket
        ticket.status = TicketStatus(triage_data.get("new_status", "IN_TRIAGE")) # FIX: Use TicketStatus Enum string input
        ticket.priority = TicketPriority(triage_data.get("new_priority", "MEDIUM")) # FIX: Use TicketPriority Enum string input
        ticket.assigned_agent = triage_data.get("next_agent", HRSDSubAgent.TRIAGE)
        
        await self._save_ticket(ticket)
        
        # CRITICAL FIX 1: Use Pydantic V2 .model_dump() with mode='json'
        payload = ticket.model_dump(mode='json') # FIX: Added mode='json'
        payload["triage_summary"] = triage_data.get("summary")
        
        # 3. Publish to queue for next agent
        await self.publisher.publish_agent_task(
            task_data=payload,
            topic=TICKET_QUEUE_TOPIC,
            key=ticket.ticket_id
        )
        return ticket

    async def resolve_ticket_by_agent(self, ticket_id: str, resolution_summary: str, resolved_by: str) -> HRSDTicket:
        """Resolves ticket."""
        ticket = await self._get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")
            
        ticket.status = TicketStatus.RESOLVED_BY_AGENT
        ticket.resolution_summary = resolution_summary
        # FIX: Ensure resolved_at is set to a proper datetime object
        ticket.resolved_at = datetime.now(timezone.utc) 
        await self._save_ticket(ticket)
        
        # CRITICAL FIX: Publish to the ServiceNow Facade 
        await self.publisher.publish_event(
            topic="HRSD_TICKET_RESOLVED",
            payload={
                "ticket_id": ticket_id, 
                "status": TicketStatus.RESOLVED_BY_AGENT.value,
                "resolution_summary": resolution_summary,
                # FIX: Send timezone-aware ISO format string for external systems
                "resolved_at": ticket.resolved_at.isoformat() 
            },
            key=ticket_id
        )
        return ticket