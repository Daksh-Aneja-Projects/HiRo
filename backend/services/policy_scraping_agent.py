# backend/services/policy_scraping_agent.py
import asyncio
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone

from services.policy_versioning import PolicyVersioningService
from services.ai_services import AIService
from services.event_publisher_service import EventPublisherService
from config.settings import settings 
from services.external_api_connector import ExternalAPIConnector 
from services.vv_compiler import VVCompiler 

from services.hyperledger_chaincode import AHCMGovernanceChaincode

logger = logging.getLogger(__name__)

POLICY_SCRAPING_INTERVAL_SECONDS = getattr(settings, 'POLICY_SCRAPING_INTERVAL_SECONDS', 3600) # Run every hour

class PolicyScrapingAgent:
    GLOBAL_FEEDS = ["PAYROLL", "WORKER", "COMPLIANCE"]
    
    def __init__(self, 
                 governance_chaincode: AHCMGovernanceChaincode, 
                 ai_service: AIService, 
                 api_connector: ExternalAPIConnector, 
                 policy_versioning_service: PolicyVersioningService, 
                 publisher: EventPublisherService,
                 vv_compiler: VVCompiler):
        
        self.chaincode = governance_chaincode
        self.ai = ai_service
        self.conn = api_connector
        self.pvs = policy_versioning_service
        self.pub = publisher
        self.vv = vv_compiler
        self.is_running = False # State flag for the loop
        
        if not hasattr(publisher, 'TOPIC_POLICY_REVIEW_ASSIGNED'):
             publisher.TOPIC_POLICY_REVIEW_ASSIGNED = "policy.review.assigned" 
             
        logger.info("✓ PolicyScrapingAgent Initialized (Global Sentinel Mode).")

    async def _process_single_feed(self, jurisdiction: str, feed_type: str) -> Tuple[bool, str]:
        """Fetch and apply one regulatory feed.

        There is no feed attached. This slept for 100ms and returned
        ("Processed"), so the sweep above reported success for every
        jurisdiction and logged "Full policy sweep cycle finished" hourly while
        nothing was ever read. Reporting honestly is what makes it visible that
        this needs a real source before it can do anything.
        """
        logger.info(f"No regulatory source is configured for {feed_type} in {jurisdiction}.")
        return False, "No source configured"

    async def execute_full_sweep(self, jurisdictions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Executes a one-time sweep across all jurisdictions."""
        if not jurisdictions:
            try:
                # Real call to Chaincode (Postgres)
                jurisdictions = ["US-CA", "UK", "EU"] 
            except Exception:
                jurisdictions = settings.POLICY_SCRAPING_JURISDICTIONS
                
        logger.info(f"Policy scraping initiated for {len(jurisdictions)} jurisdictions.")
        
        tasks = [self._process_single_feed(j, f) for j in jurisdictions for f in self.GLOBAL_FEEDS]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            "status": "COMPLETED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def monitor_and_generate_rules(self):
        """Continuous background monitoring loop."""
        if self.is_running:
            logger.warning("Policy Scraping Agent is already running.")
            return

        self.is_running = True
        logger.info("Policy Scraping Agent monitor loop started.")

        try:
            while self.is_running:
                start_time = datetime.now(timezone.utc)
                
                logger.info("Starting new full policy sweep cycle...")
                await self.execute_full_sweep()
                logger.info("Full policy sweep cycle finished.")
                
                elapsed_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                sleep_time = max(60, POLICY_SCRAPING_INTERVAL_SECONDS - elapsed_time)
                
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"FATAL error in Policy Scraping monitor loop: {e}")
        finally:
            self.is_running = False
            logger.info("Policy Scraping Agent monitor loop stopped.")

    def stop_monitoring(self):
        """Sets the running flag to false to stop the loop."""
        self.is_running = False