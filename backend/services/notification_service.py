"""Telling people what happened to their requests.

Every decision in HiRo was recorded correctly and then announced to nobody. An
employee who asked for time off saw "submitted" and had to keep re-opening the
page to find out whether their manager had decided; a manager was never told
that something new was waiting for them. The decision events published to the
message bus had no consumer and no user-facing surface at all.

This is the surface. A notification is one plain-English sentence addressed to
one person, with a link to the screen where they can act on it.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.postgres_client import pg_client

logger = logging.getLogger(__name__)

TABLE = "notifications"

# What a notification is about. The value is never shown to anyone: each
# notification carries its own written sentence.
KIND_LEAVE = "LEAVE_DECISION"
KIND_TIMESHEET = "TIMESHEET_DECISION"
KIND_EXPENSE = "EXPENSE_DECISION"
KIND_APPROVAL_WAITING = "APPROVAL_WAITING"
KIND_CASE = "CASE_UPDATE"
KIND_POLICY = "POLICY_UPDATE"


async def ensure_table() -> None:
    """Create the notifications table if it is not there yet."""
    try:
        await pg_client.execute(
            f"""CREATE TABLE IF NOT EXISTS {TABLE} (
                    notification_id TEXT PRIMARY KEY,
                    employee_uuid   TEXT NOT NULL,
                    kind            TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    body            TEXT NOT NULL,
                    link            TEXT,
                    related_id      TEXT,
                    created_at      TIMESTAMP WITH TIME ZONE NOT NULL,
                    read_at         TIMESTAMP WITH TIME ZONE
                )"""
        )
        # The only query this table serves is "my unread, newest first".
        await pg_client.execute(
            f"CREATE INDEX IF NOT EXISTS {TABLE}_recipient_idx "
            f"ON {TABLE} (employee_uuid, created_at DESC)"
        )
    except Exception as e:
        logger.warning(f"Could not prepare the notifications table: {e}")


async def notify(employee_uuid: str, kind: str, title: str, body: str,
                 link: Optional[str] = None, related_id: Optional[str] = None) -> Optional[str]:
    """Tell one person one thing.

    Never raises: failing to send a notification must not roll back the decision
    that caused it. A lost notification is a nuisance; a lost approval is not.
    """
    if not employee_uuid:
        return None
    notification_id = f"NTF-{uuid.uuid4().hex[:12].upper()}"
    try:
        await pg_client.execute(
            f"""INSERT INTO {TABLE}
                (notification_id, employee_uuid, kind, title, body, link, related_id, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            notification_id, employee_uuid, kind, title, body, link, related_id,
            datetime.now(timezone.utc),
        )
        return notification_id
    except Exception as e:
        logger.warning(f"Could not notify {employee_uuid} about {kind}: {e}")
        return None


async def notify_manager_of(employee_uuid: str, kind: str, title: str, body: str,
                            link: Optional[str] = None, related_id: Optional[str] = None) -> Optional[str]:
    """Tell whoever approves for this person that something is waiting."""
    try:
        row = await pg_client.fetchrow(
            "SELECT manager_id FROM employee_pii WHERE employee_uuid = $1", employee_uuid)
    except Exception as e:
        logger.warning(f"Could not find the manager for {employee_uuid}: {e}")
        return None
    manager_id = (row or {}).get("manager_id")
    if not manager_id:
        return None
    return await notify(manager_id, kind, title, body, link, related_id)


async def list_for(employee_uuid: str, limit: int = 50,
                   unread_only: bool = False) -> List[Dict[str, Any]]:
    """This person's notifications, newest first."""
    if not employee_uuid:
        return []
    lim = max(1, min(int(limit or 50), 200))
    where = "WHERE employee_uuid = $1" + (" AND read_at IS NULL" if unread_only else "")
    try:
        rows = await pg_client.fetch(
            f"""SELECT notification_id, kind, title, body, link, related_id, created_at, read_at
                FROM {TABLE} {where} ORDER BY created_at DESC LIMIT $2""",
            employee_uuid, lim)
    except Exception as e:
        logger.warning(f"Could not read notifications for {employee_uuid}: {e}")
        return []
    return [
        {
            "notification_id": r["notification_id"],
            "kind": r["kind"],
            "title": r["title"],
            "body": r["body"],
            "link": r["link"],
            "related_id": r["related_id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "read": r["read_at"] is not None,
        }
        for r in rows
    ]


async def unread_count(employee_uuid: str) -> int:
    if not employee_uuid:
        return 0
    try:
        row = await pg_client.fetchrow(
            f"SELECT COUNT(*) AS n FROM {TABLE} WHERE employee_uuid = $1 AND read_at IS NULL",
            employee_uuid)
        return int((row or {}).get("n") or 0)
    except Exception as e:
        logger.warning(f"Could not count notifications for {employee_uuid}: {e}")
        return 0


async def mark_read(employee_uuid: str, notification_id: Optional[str] = None) -> int:
    """Mark one notification read, or all of them when no id is given.

    Scoped to the owner, so nobody can mark somebody else's notifications read.
    """
    if not employee_uuid:
        return 0
    now = datetime.now(timezone.utc)
    try:
        if notification_id:
            result = await pg_client.execute(
                f"""UPDATE {TABLE} SET read_at = $1
                    WHERE notification_id = $2 AND employee_uuid = $3 AND read_at IS NULL""",
                now, notification_id, employee_uuid)
        else:
            result = await pg_client.execute(
                f"UPDATE {TABLE} SET read_at = $1 WHERE employee_uuid = $2 AND read_at IS NULL",
                now, employee_uuid)
    except Exception as e:
        logger.warning(f"Could not mark notifications read for {employee_uuid}: {e}")
        return 0
    # asyncpg returns a status line such as "UPDATE 3".
    try:
        return int(str(result).rsplit(" ", 1)[-1])
    except (ValueError, AttributeError):
        return 0


def decision_sentence(what: str, approved: bool, detail: str = "", by: str = "") -> str:
    """One sentence a person can read without knowing how the system works."""
    verdict = "approved" if approved else "declined"
    who = f" by {by}" if by else ""
    tail = f" {detail}" if detail else ""
    return f"Your {what} was {verdict}{who}.{tail}".replace("..", ".")
