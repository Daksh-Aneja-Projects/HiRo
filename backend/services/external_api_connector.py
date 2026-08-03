# services/external_api_connector.py
"""External API Connector: Centralized, resilient service for all platform communication with third-party systems. 
Implements advanced rate limiting, retry policies, and auditing."""
import logging
from typing import Dict, Any, List, Optional
import asyncio
import httpx # Assuming httpx for asynchronous HTTP requests
import time
from config.settings import settings
from services.internal_mock_api import InternalMockAPI 

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2.0
TIMEOUT_SECONDS = 15.0

# Mock rate limit bucket (e.g., 100 requests per minute per external system)
MOCK_RATE_LIMIT_BUCKET: Dict[str, float] = {}

class ExternalAPIConnector:
    """
    Manages resilient and auditable interaction with all external APIs.
    """
    def __init__(self, internal_mock_api: Optional[InternalMockAPI] = None):
        # httpx.AsyncClient should be initialized here for connection pooling
        self.client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
        self.internal_mock_api = internal_mock_api
        logger.info(" ✓  External API Connector Initialized (Resilience and Auditing Enabled).")

    async def _handle_rate_limiting(self, system_id: str):
        """
        Implements a simple token-bucket or time-based rate limiting check.
        """
        last_request_time = MOCK_RATE_LIMIT_BUCKET.get(system_id, 0.0)
        current_time = time.monotonic()

        # Mock limit: 1 request every 0.5 seconds
        MIN_INTERVAL = 0.5
        if current_time - last_request_time < MIN_INTERVAL:
            delay = MIN_INTERVAL - (current_time - last_request_time)
            logger.warning(f"Rate limit approaching for {system_id}. Delaying {delay:.2f}s.")
            await asyncio.sleep(delay)

        MOCK_RATE_LIMIT_BUCKET[system_id] = time.monotonic()

    async def _request_with_retry(self, method: str, url: str, system_id: str, **kwargs) -> httpx.Response:
        """
        Executes an HTTP request with exponential backoff and retry logic.
        """
        for attempt in range(MAX_RETRIES):
            # Rate limiting check is performed before the request
            await self._handle_rate_limiting(system_id)

            try:
                # 1. Execute Request
                response = await self.client.request(method, url, **kwargs)

                # 2. Check for successful status (200-299)
                if response.is_success:
                    return response
                
                # 3. Check for retryable errors (5xx or specific external errors)
                if response.status_code >= 500 or response.status_code == 429: # 429 Too Many Requests
                    raise httpx.HTTPStatusError(f"Retryable status code: {response.status_code}", request=response.request, response=response)
                
                # 4. Non-retryable error (4xx)
                response.raise_for_status()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} to {system_id} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))
                else:
                    logger.error(f"Final attempt failed for {system_id} to {url}.")
                    raise
        raise RuntimeError(f"Request to {system_id} failed after {MAX_RETRIES} retries.")

    async def fetch_regulatory_drafts(self, jurisdiction: str) -> Dict[str, Any]:
        """
        Fetches predictive legal drafts and current changes (used by PolicyScrapingAgent).
        """
        if self.internal_mock_api:
            # Use the more realistic mock response which is now async-safe
            data = await self.internal_mock_api.regulatory_feed_updates(jurisdiction)
            logger.info(f"AUDIT: Mocked regulatory fetch for {jurisdiction}. Data length: {len(data.get('updates', []))}")
            # Reformat the output to match the expected structure of PolicyScrapingAgent
            if data and data.get('updates'):
                return {
                    "current_changes": {item['policy_type']: item['text'] for item in data['updates']},
                    "predictive_drafts": {}
                }
            return {"current_changes": {}, "predictive_drafts": {}}

        # Fallback to the real API call with retry logic (Original logic)
        url = f"https://api.regtech.gov/{jurisdiction}/updates"
        try:
            response = await self._request_with_retry("GET", url, system_id="REGTECH_API")
            logger.info(f"AUDIT: Successful regulatory fetch for {jurisdiction}. Status: {response.status_code}")
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch regulatory drafts: {e}")
            return {"current_changes": None, "predictive_drafts": None}

    # --- Other External Operations (Simplified) ---
    async def fetch_data_from_legacy(self, system_id: str, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use the mock API for a deterministic chunked fetch during dev/testing."""
        # Simulate network delay before fetching mock data
        await asyncio.sleep(0.1)
        
        chunk_size = params.get("chunk_size", 10)
        # Generate slightly more realistic mock data
        records = [
            {"unique_legacy_id": f"L{i}-{system_id}", "employee_name": f"LegacyUser_{i}", "data_point": f"value_{i}"}
            for i in range(chunk_size)
        ]
        return {"records": records}
        

    async def setup_integration_connection(self, integration_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Sets up an external API connection."""
        await asyncio.sleep(0.2)
        return {"success": True, "message": f"Connection {integration_id} established."}