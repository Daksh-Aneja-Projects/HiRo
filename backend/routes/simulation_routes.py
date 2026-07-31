# /backend/routes/simulation_routes.py
"""Simulation and What-If Analysis Routes"""
import logging
from typing import Dict, Any, List 
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from pydantic import BaseModel
from datetime import datetime, timezone 
import asyncio 
import uuid 
import numpy as np 
# CRITICAL REFINEMENT: Import AuthPayload for proper type hinting if used in a standalone context
from services.auth_deps import get_auth_payload, manager_role_required 

logger = logging.getLogger(__name__)
# FIX 1: Added explicit router prefix for consistency with frontend calls (e.g., /simulation/run)
router = APIRouter(prefix="/simulation") 

# There used to be a SyntheticTwinEnginePlaceholder here that returned
# random.uniform() for risk delta, attrition change, productivity and cost, and
# was substituted silently whenever the real engine was missing from app.state.
# A wiring failure would have turned "simulation" into a random number generator
# with nothing on screen to say so, and a manager would have made a decision
# about a real person on the strength of it. It is better for the screen to say
# the simulator is unavailable.

class SimulationRequest(BaseModel):
    employee_id: str
    synthetic_adjustments: Dict[str, Any]
    simulation_type: str = "what_if"
    include_recommendations: bool = True
 
class BatchSimulationRequest(BaseModel):
    simulations: list[SimulationRequest]
    compare_results: bool = True

# FIX 2: Corrected the route path back to the simple /run (Matches frontend API: /simulation/run)
@router.post("/run")
# CRITICAL REFINEMENT: Add RBAC dependency for real-world usage consistency
async def run_what_if_simulation(request: SimulationRequest, req: Request, payload: Dict = Depends(manager_role_required)):
    """Run prescriptive what-if simulation (Matches frontend API: /simulation/run)"""
    
    engine = getattr(req.app.state, 'synthetic_twin_engine', None)
    
    if not engine:
        raise HTTPException(
            status_code=503,
            detail="The simulator is not available right now, so no result can be produced.")

    try:
        # CRITICAL REFINEMENT: Pass the user_id from the payload for auditing/access control
        result = await engine.run_simulation(
            employee_id=request.employee_id,
            adjustments=request.synthetic_adjustments,
            simulation_type=request.simulation_type,
            user_id=payload['user_id']
        )
        return result
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

# FIX 3: Corrected the batch path to be relative to the router prefix /simulation
@router.post("/batch")
# CRITICAL REFINEMENT: Add RBAC dependency
async def run_batch_simulation(request: BatchSimulationRequest, req: Request, payload: Dict = Depends(manager_role_required)):
    """Run multiple simulations and optionally compare results (Full path: /api/simulation/batch)"""
    
    engine = getattr(req.app.state, 'synthetic_twin_engine', None)
    if not engine:
        raise HTTPException(
            status_code=503,
            detail="The simulator is not available right now, so no results can be produced.")

    simulation_tasks = [
        # CRITICAL REFINEMENT: Pass the user_id from the payload to each simulation
        engine.run_simulation(
            employee_id=sim.employee_id,
            adjustments=sim.synthetic_adjustments,
            simulation_type=sim.simulation_type,
            user_id=payload['user_id']
        )
        for sim in request.simulations
    ]
    
    results = await asyncio.gather(*simulation_tasks, return_exceptions=True)
    
    # Filter out exceptions for robust processing
    successful_results = [r for r in results if not isinstance(r, Exception)]
    
    response_data = {
        "batch_id": uuid.uuid4().hex,
        "successful_simulations": len(successful_results),
        "total_simulations": len(request.simulations),
        "results": successful_results
    }
    
    if request.compare_results:
        # CRITICAL FIX: Ensure helper function is available locally or imported 
        # (Since this is a file fragment, we assume it's available or should be self-contained)
        summary = _aggregate_simulation_results(successful_results) 
        response_data['comparative_analysis'] = summary
        
    return response_data

def _aggregate_simulation_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Performs comparative analysis across multiple simulations"""
    
    if len(results) < 2:
        return {"summary": "Insufficient data for comparative analysis."} 

    # CRITICAL FIX: Robust extraction and cleaning of numeric data
    risk_deltas = [r.get("risk_score_delta", 0) for r in results]
    attrition_changes = [r.get("attrition_probability_change", 0) for r in results]
    productivity_impacts = [r.get("productivity_impact", 0) for r in results]
    
    valid_risk_deltas = [x for x in risk_deltas if isinstance(x, (int, float))]
    
    if not valid_risk_deltas:
        return {"summary": "Error calculating metrics - insufficient numeric data."}
    
    # Ensure numpy operations are on lists of compatible types
    try:
        avg_risk_delta = np.mean(valid_risk_deltas)
        avg_attrition_change = np.mean([x for x in attrition_changes if isinstance(x, (int, float))])
        avg_productivity_impact = np.mean([x for x in productivity_impacts if isinstance(x, (int, float))])
    except Exception:
        # Fallback if numpy fails due to complex types
        avg_risk_delta = sum(valid_risk_deltas) / len(valid_risk_deltas)
        avg_attrition_change = 0
        avg_productivity_impact = 0

    highest_risk_increase = max(valid_risk_deltas) if valid_risk_deltas else 0
    lowest_risk_increase = min(valid_risk_deltas) if valid_risk_deltas else 0
    
    # Safely find the most effective adjustment
    most_effective_adjustment = "N/A"
    try:
        # Note: This relies on 'productivity_impact' being a key in the returned results
        most_effective_adjustment = max(results, key=lambda x: x.get("productivity_impact", -float('inf'))).get("employee_id", "N/A")
    except ValueError:
        pass # list is empty, already handled by len(results) check

    return {
        "summary": {
            "average_risk_delta": avg_risk_delta,
            "average_attrition_change": avg_attrition_change,
            "average_productivity_impact": avg_productivity_impact,
            "highest_risk_increase": highest_risk_increase,
            "lowest_risk_increase": lowest_risk_increase,
            "most_effective_adjustment": most_effective_adjustment
        },
        "recommendations": [
            "Focus on adjustments with highest productivity impact",
            "Monitor simulations with high risk increases"
        ]
    }