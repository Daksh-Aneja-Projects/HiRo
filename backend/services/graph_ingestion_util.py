# /backend/services/graph_ingestion_util.py - FIXED
# services/graph_ingestion_util.py
import logging
import asyncio
import time
from typing import Dict, Any, Optional # CRITICAL FIX: Add missing imports
import requests
from urllib.parse import urlparse
from config.settings import settings

logger = logging.getLogger(__name__)

# Constants
DGRAPH_URL = getattr(settings, 'DGRAPH_URL', "http://dgraph-alpha:8080")
MAX_RETRIES = 3

class GraphIngestionUtil:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = self._clean_url(DGRAPH_URL)
        self.mutate_url = f"{self.base_url}/mutate?commitNow=true"

    def _clean_url(self, url: str) -> str:
        # Handle Pydantic SecretStr or raw string
        url_str = url.get_secret_value() if hasattr(url, 'get_secret_value') else str(url) 
        if not urlparse(url_str).scheme:
            return f"http://{url_str}"
        return url_str.rstrip("/")

    def _request(self, payload: Dict) -> Dict:
        for i in range(MAX_RETRIES):
            try:
                resp = self.session.post(self.mutate_url, json=payload, timeout=5)
                if 
                resp.status_code == 200:
                    return {"success": True, "data": resp.json()}
            except Exception as e:
                logger.warning(f"Dgraph attempt {i+1} failed: {e}")
                time.sleep(0.5)
        return {"success": False, "error": "Max retries reached"}

    # --- Async Wrappers for 
    # Agent Usage ---
    async def async_create_employee_node(self, emp_id: str, name: str, role: str) -> Dict:
        mutation = {"set": [{"uid": f"_:emp_{emp_id}", "dgraph.type": "Employee", "name": name, "role": role}]}
        # CRITICAL FIX: The use of synchronous requests needs to be wrapped in asyncio.to_thread, which it is.
        return await asyncio.to_thread(self._request, mutation)

    async def async_create_reports_to_relationship(self, emp_id: str, mgr_id: str) -> Dict:
        mutation = {"set": [{"uid": f"_:emp_{emp_id}", "reports_to": {"uid": f"_:emp_{mgr_id}"}}]}
        # CRITICAL FIX: The use of synchronous requests needs to be wrapped in asyncio.to_thread, which it is.
        return await asyncio.to_thread(self._request, mutation)

# Singleton
graph_util = GraphIngestionUtil()