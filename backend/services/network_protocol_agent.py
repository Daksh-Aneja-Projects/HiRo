# services/network_protocol_agent.py
import time
import logging
import random
from typing import Dict, Any

logger = logging.getLogger(__name__)

class NPAgent:
    def __init__(self):
        logger.info("✓ NPAgent Initialized.")

    def run_health_check(self, topic: str) -> Dict[str, Any]:
        """Deterministic simulation based on topic hash."""
        seed = sum(ord(c) for c in topic) + int(time.time() / 10) # Change every 10s
        random.seed(seed)
        
        latency = random.uniform(5, 45)
        error_rate = random.uniform(0, 0.02)
        
        status = "HEALTHY"
        if latency > 40: status = "WARNING"
        if error_rate > 0.01: status = "DEGRADED"

        return {
            "topic": topic,
            "latency_ms": round(latency, 2),
            "error_rate": round(error_rate, 4),
            "status": status,
            "checked_at": time.time()
        }