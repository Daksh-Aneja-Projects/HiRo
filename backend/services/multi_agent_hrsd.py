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

    async def _save_ticket(self, ticket: HRSDTicket):
        # NOTE: This assumes the HRSDTicket model matches the Postgres table structure
        ticket_data = ticket.model_dump(mode='json') # FIX: Use model_dump(mode='json')
        
        # This is a mock DB call for brevity, but should perform UPSERT in production
        logger.info(f"Mock Save to Postgres for ticket: {ticket.ticket_id}")

    async def _get_ticket(self, ticket_id: str) -> Optional[HRSDTicket]:
        # NOTE: Mock retrieval
        if ticket_id == "T-404": return None
        return HRSDTicket(
            ticket_id=ticket_id,
            employee_id="EMP-001",
            subject="Mock Ticket",
            status=TicketStatus.NEW,
            priority=TicketPriority.MEDIUM,
            created_at=datetime.now(timezone.utc)
        )

    async def create_ticket(self, employee_id: str, subject: str, description: str) -> HRSDTicket:
        new_ticket = HRSDTicket(
            ticket_id=f"T-{uuid.uuid4().hex[:8].upper()}",
            employee_id=employee_id,
            subject=subject,
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

    async def triage_ticket(self, ticket_id: str) -> HRSDTicket:
        """AI-driven triage, assigns priority and next agent."""
        ticket = await self._get_ticket(ticket_id)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found.")

        # 1. AI Triage Mock
        triage_data = {
            "new_status": "IN_TRIAGE",
            "new_priority": "HIGH",
            "next_agent": HRSDSubAgent.IT_SUPPORT,
            "summary": "IT system access issue."
        }
        
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
            event_data={
                "ticket_id": ticket_id, 
                "status": TicketStatus.RESOLVED_BY_AGENT.value,
                "resolution_summary": resolution_summary,
                # FIX: Send timezone-aware ISO format string for external systems
                "resolved_at": ticket.resolved_at.isoformat() 
            },
            key=ticket_id
        )
        return ticket