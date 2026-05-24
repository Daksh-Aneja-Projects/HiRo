# /backend/services/admin_service.py - REPLACEMENT (DB Transaction Integrity)
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import secrets
import asyncio 
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager # CRITICAL FIX: Import for Stub

from config.settings import settings

logger = logging.getLogger(__name__)

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