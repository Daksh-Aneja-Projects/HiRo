# services/utility_agents.py - REPLACEMENT (Precision and Input Validation)
"""
Utility Agents: Logic-based calculators for Cost and Quality.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
import random 

logger = logging.getLogger(__name__)

class TCOReductionAgent:
    def __init__(self):
        logger.info("✅ TCOReductionAgent Initialized.")
        
    def generate_cost_forecast(self, workload: str, current_cost: float = 1000.0) -> Dict[str, Any]:
        """Calculates savings based on standard automation multipliers."""
        
        # CRITICAL FIX: Robust input casting
        try:
            current_cost = float(current_cost)
        except (ValueError, TypeError):
            logger.error("Invalid current_cost provided. Defaulting to 1000.0.")
            current_cost = 1000.0
            
        # Logic: Automation typically saves 30-40% on Ops
        savings_factor = 0.35
        automated_cost = current_cost * (1 - savings_factor)
        
        # CRITICAL FIX: Ensure output is rounded for financial reports
        return {
            "workload": workload,
            "baseline_cost": round(current_cost, 2),
            "projected_cost": round(automated_cost, 2),
            "annual_savings": round((current_cost - automated_cost) * 12, 2),
            "roi_months": 4.5 
        }

class QualityOrchestrationAgent:
    def __init__(self):
        logger.info("✅ QualityOrchestrationAgent Initialized.")
        
    def run_quality_gate_check(self, deployment_id: str, code_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Deterministic gate check based on input metrics."""
        
        # CRITICAL FIX: Robustly retrieve and cast metrics
        try:
            coverage = float(code_metrics.get('coverage', 0.0))
            bugs = int(code_metrics.get('critical_bugs', 0))
        except (ValueError, TypeError):
            logger.error(f"Invalid metrics provided for {deployment_id}. Failing gate.")
            return {
                "deployment_id": deployment_id,
                "gate_status": "FAILED_INPUT_ERROR",
                "blockers": ["Invalid metric input type."]
            }
            
        passed = coverage > 80.0 and bugs == 0
        
        blockers: List[str] = []
        if coverage <= 80.0:
            blockers.append(f"Low Coverage ({coverage:.1f}%)")
        if bugs > 0:
            blockers.append(f"{bugs} Critical Bugs Detected")
            
        return {
            "deployment_id": deployment_id,
            "gate_status": "PASSED" if passed else "FAILED",
            "blockers": blockers
        }

tco_agent = TCOReductionAgent()
quality_agent = QualityOrchestrationAgent()