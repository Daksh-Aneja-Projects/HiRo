# /backend/services/postgres_client.py - REPLACEMENT (Ignoring the erroneous batch_size parameter)
"""Postgres Client Service: High-performance, asynchronous data access layer.
Uses asyncpg connection pooling and robust transaction management."""
import logging
import asyncio
import json
from typing import Optional, Dict, Any, List, Tuple, Union
from contextlib import asynccontextmanager

try:
    import asyncpg
    from asyncpg import Pool 
except ImportError:
    # CRITICAL FIX: Ensure the import error is correctly handled
    raise RuntimeError("Critical Dependency Missing: Please run 'pip install asyncpg'")

from config.settings import settings

logger = logging.getLogger(__name__)

# CRITICAL FIX: Use settings.postgres_url() to build the connection 
DATABASE_URL = settings.postgres_url() 

class PostgresClient:
    """
    Production-grade AsyncPG wrapper with Connection Pooling. 
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PostgresClient, cls).__new__(cls)
            cls._instance.pool: Optional[Pool] = None # Explicitly type pool
            cls._instance.is_connected = False 
        return cls._instance
        
    async def connect(self, db_url: Optional[str] = None):
        """Initializes the asyncpg connection pool."""
        if self.pool and self.is_connected: 
            return
        
        conn_url = db_url if db_url else DATABASE_URL
        
        try:
            # Sanitize log message
            log_url = conn_url.split('@')[-1] if '@' in conn_url else conn_url
            logger.info(f"Connecting to Postgres: {log_url}") 
            
            self.pool = await asyncpg.create_pool(
                dsn=conn_url,
                min_size=5,
                max_size=20,
                command_timeout=60,
                # CRITICAL FIX: Add explicit loop for compatibility
                loop=asyncio.get_event_loop() 
            )
            self.is_connected = True 
            logger.info("✅ Postgres Connection Pool Established.")
        except Exception as e:
            self.is_connected = False 
            logger.critical(f"❌ Failed to connect to Postgres: {e}")
            raise

    async def close(self):
        """Closes the pool."""
        if self.pool and self.is_connected:
            await self.pool.close()
            self.is_connected = False 
            logger.info("Postgres Pool closed.") 

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Executes a SELECT query and returns a list of dictionaries."""
        if not self.pool:
            await self.connect() 
            
        async with self.pool.acquire() as conn:
            try:
                records = await conn.fetch(query, *args)
                return [dict(r) for r in records]
                
            except Exception as e:
                logger.error(f"Query Failed: {query[:50]}... | Error: {e}") 
                raise

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Executes a SELECT query and returns a single row."""
        if not self.pool:
            await self.connect()
            
        async with self.pool.acquire() as conn:
            try:
                record = await conn.fetchrow(query, *args)
                return dict(record) if record else None
            except Exception as e:
                logger.error(f"Fetchrow Failed: {query[:50]}... | Error: {e}") 
                raise

    async def execute(self, query: str, *args) -> str:
        """Executes an INSERT/UPDATE/DELETE command."""
        if not self.pool:
            await self.connect()
            
        async with self.pool.acquire() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as e:
                logger.error(f"Execute Failed: {query[:50]}... | Error: {e}") 
                raise

    # CRITICAL FIX: Modify the signature to accept 'batch_size' (and any other extraneous args)
    # but ignore them, as the underlying asyncpg.executemany doesn't use them.
    async def executemany_async(self, query: str, args_list: List[Union[Tuple, Dict[str, Any]]], **kwargs) -> None:
        """Executes a command using many parameter sets for bulk insertion."""
        if 'batch_size' in kwargs:
             logger.warning("Ignoring 'batch_size' parameter in PostgresClient.executemany_async; bulk insert handled by asyncpg.")
             
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as conn:
            try:
                # Use conn.executemany for efficiency
                await conn.executemany(query, args_list)
            except Exception as e:
                logger.error(f"Executemany Failed (Bulk Insert): {query[:50]}... | Error: {e}") 
                raise

    @asynccontextmanager
    async def transaction(self, requesting_agent_id: str, purpose: str = "general_op"):
        """
        Transactional Context Manager with Audit Context. Ensures atomicity.
        """
        if not self.pool:
            await self.connect()
            
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    yield conn
                except Exception as e:
                    # CRITICAL FIX: Log the rollback for security/audit purposes
                    logger.error(f"TRANSACTION ROLLBACK ({requesting_agent_id}/{purpose}): {type(e).__name__}: {e}")
                    raise

# Global instance
pg_client = PostgresClient()