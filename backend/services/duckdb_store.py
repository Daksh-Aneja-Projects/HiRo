# services/duckdb_store.py
"""
DuckDB UDM Store - Deprecated Stub.
Maintains API compatibility for legacy imports but performs no operations.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Safe settings import
try:
    from config.settings import settings 
    DB_PATH = getattr(settings, 'DUCKDB_PATH', "/app/backend/data/hiro_udm.duckdb")
except ImportError:
    DB_PATH = "/app/backend/data/hiro_udm.duckdb"

class DuckDBStore:
    """
    Deprecated placeholder. 
    The application has migrated to Postgres (pgvector).
    This class exists to prevent ImportErrors in legacy code paths.
    """
    def __init__(self, db_path: str = DB_PATH):
        # Changed from CRITICAL to INFO to stop log noise
        logger.info("ℹ️ Legacy DuckDBStore initialized (Stub Mode). I/O redirected to Postgres.")

    def initialize_schema(self):
        """No-op."""
        pass

    def get_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Returns None to force caller to handle missing data gracefully."""
        return None

    def get_leave_balance(self, employee_id: str) -> Optional[Dict[str, Any]]:
        return None
            
    def search_similar_records(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Returns empty list to prevent iteration errors."""
        return []

    def log_policy_decision(self, audit_data: Dict[str, Any]):
        """Silently ignore legacy logs."""
        pass

    def insert_ingested_records(self, records: List[Dict[str, Any]]):
        """Silently ignore legacy writes."""
        pass

    def update_leave_balance(self, employee_id: str, new_balance_hours: float, new_used_hours: float):
        pass

    def close(self):
        pass

# Global instance
udm_store = DuckDBStore()
