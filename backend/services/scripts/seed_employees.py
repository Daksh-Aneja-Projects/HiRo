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
        "created_at": datetime.now(timezone.utc), # FIX: Pass datetime object
        "status": "NEW",
        "assigned_agent": None,
        "priority": "NORMAL",
        "subject": "Seeded ticket 1",
        "description": "This is a seeded ticket for initial environment."
    },
    {
        "ticket_id": "TICKET-0002",
        "created_at": (datetime.now(timezone.utc)), # FIX: Pass datetime object
        "status": "TRIAGE",
        "assigned_agent": "auto-responder",
        "priority": "NORMAL",
        "subject": "Seeded ticket 2",
        "description": "Second seeded ticket."
    }
]


async def run_seeder(database_url: str, seed_example_rows: bool = True):
    """
    Connect to Postgres and ensure hrsd_tickets table exists. Optionally seed example rows.
    """
    if not database_url:
        raise ValueError("DATABASE_URL must be set (postgres://user:pass@host:port/dbname)")

    conn = None
    try:
        logger.info("Connecting to Postgres: %s", database_url)
        conn = await asyncpg.connect(database_url)

        logger.info("Creating hrsd_tickets table (if not exists)...")
        await conn.execute(DDL_HRSD_TICKETS)
        await conn.execute(IDX_HRSD_TICKETS)

        if seed_example_rows:
            logger.info("Seeding example rows (idempotent)...")
            # Use INSERT ... ON CONFLICT DO NOTHING to remain idempotent
            insert_sql = """
            INSERT INTO public.hrsd_tickets(ticket_id, created_at, status, assigned_agent, priority, subject, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7) 
            ON CONFLICT (ticket_id) DO NOTHING
            """
            for r in SEED_ROWS:
                # created_at is now a datetime object, removing the redundant cast in the SQL
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
    except Exception as e:
        logger.exception("Seeder failed: %s", e)
        raise
    finally:
        if conn:
            await conn.close()


def main():
    database_url = os.getenv("DATABASE_URL") or os.getenv("PG_CONN") or "postgres://postgres:postgres@localhost:5432/postgres"
    # Choose whether to seed example rows; set to False in production if not needed
    seed_example = os.getenv("SEED_EXAMPLE_ROWS", "true").lower() in ("1", "true", "yes")
    asyncio.run(run_seeder(database_url, seed_example_rows=seed_example))


if __name__ == "__main__":
    main()