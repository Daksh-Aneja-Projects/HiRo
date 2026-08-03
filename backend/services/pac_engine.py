# backend/services/pac_engine.py
"""
Performance Analysis & Correction (PAC) Engine.
Integrates the high-performance Rust extension (pac_engine_rs) and provides
Python-native fallback and orchestration logic.
"""
import logging
from typing import Dict, Any, List, Optional
import json

try:
    from pac_engine_rs import calculate_pac_score as rust_calculate_pac_score 
    RUST_ENABLED = True
    logger = logging.getLogger(__name__)
    logger.info("Rust-based PAC Engine (pac_engine_rs) is enabled and correctly linked.")
except ImportError:
    # Fallback to Python implementation if Rust extension is unavailable
    RUST_ENABLED = False
    logger = logging.getLogger(__name__)
    logger.warning("Rust-based PAC Engine (pac_engine_rs) not found. Falling back to Python implementation. Performance may be degraded.")
    
# =========================================================================
# Python Fallback Implementation (remains unchanged and robust)
# =========================================================================
def python_calculate_pac_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Python-native implementation of the PAC score calculation.
    """
    
    try:
        total_tasks = max(0, int(metrics.get('total_tasks', 0)))
        completed_tasks = max(0, int(metrics.get('completed_tasks', 0)))
        bug_rate = max(0.0, float(metrics.get('bug_rate', 0.0))) 
        client_satisfaction = max(0.0, float(metrics.get('client_satisfaction', 0.0)))
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid input metrics provided to PAC Engine: {e}")
        return {
            "pac_score": 0.0,
            "performance_tier": "Critical Intervention Required - Invalid Data",
            "error": str(e)
        }
    
    # 1. Completion Ratio (Weight: 40%)
    if total_tasks > 0:
        completion_ratio = min(1.0, completed_tasks / total_tasks) # Cap at 1.0
    else:
        # If no tasks were assigned/completed, assume perfect completion for neutrality
        completion_ratio = 1.0
    
    # 2. Quality Score (Based on Bug Rate - Weight: 30%)
    # Assuming bug_rate is a percentage (e.g., 5 for 5 for 5%)
    # Scale: 0% bugs = 1.0 score; 10% bugs = 0.9 score.
    quality_score = max(0.0, 1.0 - (bug_rate / 100.0))
    
    # 3. Client Satisfaction (Weight: 30%)
    # Normalize client satisfaction to a 0.0-1.0 range (assuming input max is 100)
    if client_satisfaction > 1.0:
        client_satisfaction_score = min(1.0, client_satisfaction / 100.0)
    else:
        client_satisfaction_score = min(1.0, client_satisfaction)
        
    # Calculate weighted PAC Score (out of 100)
    pac_score = (completion_ratio * 40) + (quality_score * 30) + (client_satisfaction_score * 30)
    
    final_pac_score = max(0.0, min(100.0, pac_score))
    
    # Determine Performance Tier
    if final_pac_score >= 90:
        performance_tier = "Exceeds Expectations"
    elif final_pac_score >= 75:
        performance_tier = "Meets Expectations"
    elif final_pac_score >= 50:
        performance_tier = "Needs Improvement"
    else:
        performance_tier = "Critical Intervention Required"
        
    return {
        "pac_score": round(final_pac_score, 2),
        "performance_tier": performance_tier
    }
# =========================================================================
# Public Engine Interface
# =========================================================================
def calculate_pac_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public function to calculate the PAC score, using Rust if available.
    """
    if RUST_ENABLED:
        try:
            metrics_json = json.dumps(metrics)
            
            # Call the Rust function
            result_json_string = rust_calculate_pac_score(metrics_json)
            
            # Deserialize the result string back to a Python dictionary
            return json.loads(result_json_string) 

        except Exception as e:
            logger.error(f"Rust PAC engine failed with error: {type(e).__name__}: {e}. Falling back to Python implementation.")
            return python_calculate_pac_score(metrics)
    else:
        return python_calculate_pac_score(metrics)
# Example usage and testing function (optional, for development)
if __name__ == "__main__":
    # Test cases removed for brevity but the logic remains sound
    pass