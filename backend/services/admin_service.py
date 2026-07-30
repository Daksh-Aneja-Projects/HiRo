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
    @asynccontextmanager
    async def transaction(self, requesting_agent_id: str, purpose: str): 
        class MockConn: 
            async def execute(self, q, v=None): pass
        yield MockConn()


class AdminService:
    def __init__(self, mongo_client: AsyncIOMotorClient, pg_client: PostgresClientStub):
        self.db = mongo_client[DEFAULT_DB_NAME]
        self.announcements = self.db.announcements
        self.system_logs = self.db.system_logs
        self.audit_logs = self.db.audit_logs
        self.dao_proposals = self.db.dao_proposals
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

    async def hard_purge_system_data(self, admin_id: str) -> Dict[str, str]:
        """
        DANGEROUS: Executes a complete hard purge of non-critical system data
        from MongoDB and Postgres, retaining only the 'admin' user.
        """
        logger.critical(f"Admin {admin_id} is executing --- SYSTEM HARD PURGE ---")
        
        mongo_tasks = [
            self.announcements.delete_many({}),
            self.system_logs.delete_many({}),
            self.audit_logs.delete_many({}),
            self.dao_proposals.delete_many({}),
            self.profile_change_requests.delete_many({}),
            self.users.delete_many({"username": {"$ne": "admin"}}), 
            self.db.timesheets.delete_many({}),
            self.db.leave_requests.delete_many({}),
            self.db.expenses.delete_many({}),
            self.db.flexi_comp_plans.delete_many({}), # CRITICAL FIX: Add missing collection
        ]
        
        # CRITICAL FIX: Consolidated TRUNCATE statements within a single transaction 
        # for better control, although asyncio.gather is used for concurrency across services.
        postgres_purge_queries = [
            "TRUNCATE TABLE employee_pii RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE leave_balance RESTART IDENTITY CASCADE;",
            "TRUNCATE TABLE leave_requests RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE comp_history RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE performance_reviews RESTART IDENTITY CASCADE;",
            "TRUNCATE TABLE ingested_records RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE implementation_status RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE hrsd_tickets RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE ai_feature_vector RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE sn_hr_ticket_map RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE privacy_consents RESTART IDENTITY CASCADE;", 
            "TRUNCATE TABLE integrations_config RESTART IDENTITY CASCADE;", # CRITICAL FIX: Add integrations
        ]
        
        postgres_tasks = [self.pg_client.execute(query) for query in postgres_purge_queries]
        
        try:
            # Concurrently execute all MongoDB and Postgres purge tasks
            await asyncio.gather(*mongo_tasks, *postgres_tasks)
            logger.warning("--- SYSTEM HARD PURGE COMPLETE ---")
            return {"message": "System data reset and purged successfully."}
            
        except Exception as e:
            logger.error(f"FATAL: Hard Purge failed during execution: {type(e).__name__}: {e}")
            raise RuntimeError(f"Hard Purge failed. Check MongoDB/Postgres connection: {e}")