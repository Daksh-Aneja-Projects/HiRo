# services/workforce_health_monitoring_agent.py
import logging
from typing import Dict, Any
from datetime import datetime, timezone
import random
from config.settings import settings

logger = logging.getLogger(__name__)

# Constants
WHMA_BURNED_OUT_THRESHOLD = getattr(settings, 'WHMA_BURNED_OUT_THRESHOLD', 0.75)
WHMA_WORK_HOURS_THRESHOLD = getattr(settings, 'WHMA_WORK_HOURS_THRESHOLD', 55)

class WHMAgent:
    def __init__(self):
        logger.info("✓ WHMAgent Initialized.")

    def detect_burnout_risk(self, employee_id: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates burnout score based on work hours and sleep."""
        
        try:
            hours = float(telemetry.get('average_weekly_hours', 40.0))
            sleep = float(telemetry.get('average_sleep_hours', 7.5))
        except (ValueError, TypeError):
            logger.error(f"Invalid telemetry data for {employee_id}. Using default values.")
            hours = 40.0
            sleep = 7.5
            
        # 2. Calculate Risk (Heuristic)
        risk = 0.1 # Base risk
        
        # Hours component (Risk increases linearly past threshold)
        if hours > WHMA_WORK_HOURS_THRESHOLD:
            risk += (hours - WHMA_WORK_HOURS_THRESHOLD) * 0.05
        
        # Sleep component (Risk increases inversely below 6.0 hours)
        if sleep < 6.0:
            risk += (6.0 - sleep) * 0.1
        
        final_score = max(0.0, min(1.0, risk))
        
        return {
            "employee_id": employee_id,
            "burnout_score": round(final_score, 3), # Increased precision
            "risk_level": "CRITICAL" if final_score > WHMA_BURNED_OUT_THRESHOLD else "NORMAL",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

whm_agent = WHMAgent()