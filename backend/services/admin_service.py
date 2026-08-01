# /backend/services/admin_service.py - REPLACEMENT (DB Transaction Integrity)
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import secrets
import asyncio 
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager # CRITICAL FIX: Import for Stub

from config.settings import settings
from services.auth_service import PasswordHasher

logger = logging.getLogger(__name__)

VALID_ROLES = {"hrit_admin", "hrbp", "manager", "employee"}
PUBLIC_USER_FIELDS = {"_id": 0, "hashed_password": 0}

DEFAULT_DB_NAME = settings.MONGO_DB_NAME if hasattr(settings, 'MONGO_DB_NAME') else "ahcm_db"
MAX_USER_FETCH_LIMIT = 5000

# CRITICAL FIX: Stub for the imported PostgresClient to satisfy type-checking/injection.
class PostgresClientStub:
    """Stub for the injected PostgresClient to satisfy type-checking."""
    async def execute(self, query: str, values: Optional[List[Any]] = None) -> Any: ...
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]: ...
    @asynccontextmanager
    async def transaction(self, requesting_agent_id: str, purpose: str):
        class MockConn:
            async def execute(self, q, v=None): pass
        yield MockConn()


# Every Postgres table the purge is allowed to empty. Ordered child-before-parent
# so a single TRUNCATE ... CASCADE reads sensibly; existence is checked at run
# time because a deployment that never created a table must not turn the whole
# purge into an UndefinedTableError. The previous list named five tables that do
# not exist in any HiRo schema, so this endpoint always returned a 500 and never
# purged anything at all.
PURGE_TABLES = (
    "leave_requests",
    "leave_balance",
    "comp_history",
    "performance_reviews",
    "hrsd_tickets",
    "implementation_status",
    "policy_audit_log",
    "notifications",
    "dao_proposals",
    "employee_pii",
)


class AdminService:
    def __init__(self, mongo_client: AsyncIOMotorClient, pg_client: PostgresClientStub):
        self.db = mongo_client[DEFAULT_DB_NAME]
        self.announcements = self.db.announcements
        self.system_logs = self.db.system_logs
        self.audit_logs = self.db.audit_logs
        self.profile_change_requests = self.db.profile_change_requests
        self.users = self.db.users
        self.pg_client = pg_client 
    
    async def get_all_users(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """Real user directory from Mongo (never the password hash)."""
        limit = max(1, min(int(limit or 200), MAX_USER_FETCH_LIMIT))
        offset = max(0, int(offset or 0))
        cursor = self.users.find({}, PUBLIC_USER_FIELDS).sort("username", 1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        username = (data.get("username") or "").strip().lower()
        role = (data.get("role") or "").strip().lower()
        if not username:
            raise ValueError("username is required")
        if role not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        if await self.users.find_one({"username": username}):
            raise ValueError(f"user '{username}' already exists")

        # Default password == username, matching the dev-login convention.
        password = data.get("password") or username
        doc = {
            "username": username,
            "email": (data.get("email") or f"{username}@hiro.ai").strip(),
            "full_name": (data.get("full_name") or username.title()).strip(),
            "role": role,
            "employee_uuid": data.get("employee_uuid"),
            "is_active": bool(data.get("is_active", True)),
            "hashed_password": PasswordHasher.hash_password(password),
            "user_id": str(secrets.randbits(64)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.users.insert_one(doc)
        doc.pop("_id", None)
        doc.pop("hashed_password", None)
        return {"status": "Created", "user": doc}

    async def update_role(self, username: str, role: str) -> Dict[str, Any]:
        role = (role or "").strip().lower()
        if role not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}")
        result = await self.users.update_one({"username": username}, {"$set": {"role": role}})
        if result.matched_count == 0:
            raise ValueError(f"user '{username}' not found")
        return {"status": "Updated", "username": username, "new_role": role}

    async def delete_user(self, username: str) -> Dict[str, Any]:
        if username == "admin":
            raise ValueError("the built-in 'admin' account cannot be deleted")
        result = await self.users.delete_one({"username": username})
        if result.deleted_count == 0:
            raise ValueError(f"user '{username}' not found")
        return {"status": "Deleted", "username": username}

    async def get_announcements(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 50), 500))
        offset = max(0, int(offset or 0))
        cursor = self.announcements.find({}, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
        return await cursor.to_list(length=limit)

    async def create_announcement(self, data: Dict[str, Any], author: str = "system") -> Dict[str, Any]:
        title = (data.get("title") or "").strip()
        content = (data.get("content") or data.get("body") or "").strip()
        if not title or not content:
            raise ValueError("title and content are required")
        doc = {
            "id": f"ANN-{secrets.token_hex(4)}",
            "title": title,
            "content": content,
            "author": author,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.announcements.insert_one(dict(doc))
        return {"status": "Published", "announcement": doc}

    # Mongo collections the purge empties. dao_proposals is deliberately absent:
    # governance proposals live in Postgres (hyperledger_chaincode writes them
    # there), and the Mongo collection of the same name is never written, so
    # dropping it looked like a purge while the real five rows survived.
    MONGO_PURGE_COLLECTIONS = (
        "announcements", "system_logs", "audit_logs", "profile_change_requests",
        "timesheets", "leave_requests", "expenses", "flexi_comp_plans",
    )

    async def hard_purge_system_data(self, admin_id: str) -> Dict[str, Any]:
        """
        DANGEROUS: Executes a complete hard purge of non-critical system data
        from MongoDB and Postgres, retaining only the 'admin' user.

        Reports per-store results honestly: a table that does not exist is
        reported as skipped, not silently counted as purged, and a failure in
        one store does not hide what the other store actually did.
        """
        logger.critical(f"Admin {admin_id} is executing --- SYSTEM HARD PURGE ---")

        postgres_report = await self._purge_postgres()
        mongo_report = await self._purge_mongo()

        failures = ([t for t, s in postgres_report.items() if s.startswith("failed")]
                    + [c for c, s in mongo_report.items() if s.startswith("failed")])

        if failures:
            logger.error(f"Hard Purge completed with failures: {failures}")
        else:
            logger.warning("--- SYSTEM HARD PURGE COMPLETE ---")

        return {
            "message": ("System data purged." if not failures
                        else f"System purge finished with {len(failures)} failure(s); see details."),
            "purged_cleanly": not failures,
            "postgres": postgres_report,
            "mongo": mongo_report,
        }

    async def _purge_postgres(self) -> Dict[str, str]:
        """TRUNCATE every purge-listed table that actually exists, in one statement."""
        try:
            rows = await self.pg_client.fetch(
                """SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = ANY($1::text[])""",
                list(PURGE_TABLES),
            )
        except Exception as e:
            logger.error(f"Hard Purge: could not read the table list: {type(e).__name__}: {e}")
            return {t: f"failed: table list unreadable ({type(e).__name__})" for t in PURGE_TABLES}

        present = {r["table_name"] for r in (rows or [])}
        report = {t: ("does not exist; skipped" if t not in present else "purged")
                  for t in PURGE_TABLES}
        if not present:
            return report

        ordered = [t for t in PURGE_TABLES if t in present]
        # One statement, so the purge is atomic: either every table is empty or none is.
        statement = f"TRUNCATE TABLE {', '.join(ordered)} RESTART IDENTITY CASCADE;"
        try:
            await self.pg_client.execute(statement)
        except Exception as e:
            logger.error(f"Hard Purge: Postgres TRUNCATE failed: {type(e).__name__}: {e}")
            for t in ordered:
                report[t] = f"failed: {type(e).__name__}: {e}"
        return report

    async def _purge_mongo(self) -> Dict[str, str]:
        names = list(self.MONGO_PURGE_COLLECTIONS) + ["users"]
        tasks = [self.db[c].delete_many({}) for c in self.MONGO_PURGE_COLLECTIONS]
        # The built-in admin account is the one thing that must survive.
        tasks.append(self.users.delete_many({"username": {"$ne": "admin"}}))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        report: Dict[str, str] = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(f"Hard Purge: Mongo '{name}' failed: {type(result).__name__}: {result}")
                report[name] = f"failed: {type(result).__name__}: {result}"
            else:
                report[name] = f"purged {getattr(result, 'deleted_count', 0)} document(s)"
        return report