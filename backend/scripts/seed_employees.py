# /backend/services/scripts/seed_employees.py - FINAL SYNCHRONIZED VERSION
"""
seed_employees.py
Idempotent seeder that ensures hrsd_tickets table exists and (optionally) seeds sample rows.
"""

import asyncio
import os
import logging
from datetime import datetime, timezone

import asyncpg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


DDL_HRSD_TICKETS = """
CREATE TABLE IF NOT EXISTS public.hrsd_tickets (
    ticket_id TEXT PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'NEW',
    assigned_agent TEXT,
    priority TEXT DEFAULT 'NORMAL',
    subject TEXT,
    description TEXT,
    metadata JSONB
);
"""

# Optional index to speed up SLA queries (created_at + status)
IDX_HRSD_TICKETS = """
CREATE INDEX IF NOT EXISTS idx_hrsd_tickets_status_created_at
ON public.hrsd_tickets (status, created_at);
"""

# Example seed rows (idempotent)
SEED_ROWS = [
    {
        "ticket_id": "TICKET-0001",
        "created_at": datetime.now(timezone.utc), 
        "status": "NEW",
        "assigned_agent": "HR_Triage_Agent",
        "priority": "HIGH",
        "subject": "Missing Paycheck Q4 2025",
        "description": "Employee reported missing payment for the last period.",
        "metadata": {}
    },
    {
        "ticket_id": "TICKET-0002",
        "created_at": datetime.now(timezone.utc) - timedelta(days=1),
        "status": "IN_RESOLUTION",
        "assigned_agent": "IT_Support_Agent",
        "priority": "NORMAL",
        "subject": "Laptop Replacement Request",
        "description": "Request for a replacement laptop due to hardware failure.",
        "metadata": {}
    },
]


async def run_seeder(database_url: str, seed_example_rows: bool = True):
    """
    Connects to Postgres and runs DDL/inserts idempotently.
    """
    conn = None
    try:
        logger.info(f"Connecting to database: {database_url.split('@')[-1]}")
        conn = await asyncpg.connect(database_url)

        # 1. Create Schema/Tables
        logger.info("Ensuring hrsd_tickets table exists...")
        await conn.execute(DDL_HRSD_TICKETS)
        await conn.execute(IDX_HRSD_TICKETS)
        
        # 2. Seed Rows (if enabled)
        if seed_example_rows:
            logger.info("Inserting example rows (idempotent)...")
            # Use INSERT ... ON CONFLICT DO NOTHING to remain idempotent
            insert_sql = """
            INSERT INTO public.hrsd_tickets(ticket_id, created_at, status, assigned_agent, priority, subject, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (ticket_id) DO NOTHING
            """
            for r in SEED_ROWS:
                await conn.execute(
                    insert_sql,
                    r["ticket_id"],
                    r["created_at"],
                    r["status"],
                    r["assigned_agent"],
                    r["priority"],
                    r["subject"],
                    r["description"],
                )

        logger.info("Seeder completed successfully.")
    except asyncpg.exceptions.InvalidPasswordError as e:
        logger.error(f"FATAL CREDENTIAL ERROR: {e}")
        # Re-raise the exception to be caught by init_test_data.py to trigger sys.exit(1)
        raise
    except Exception as e:
        logger.exception("Seeder failed: %s", e)
        raise
    finally:
        if conn:
            await conn.close()


def main():
    database_url = os.getenv("DATABASE_URL") or os.getenv("PG_CONN") or "postgres://postgres:postgres@localhost:5432/postgres"
    seed_example = os.getenv("SEED_EXAMPLE_ROWS", "true").lower() in ("1", "true", "yes")
    asyncio.run(run_seeder(database_url, seed_example_rows=seed_example))


if __name__ == "__main__":
    main()