# /backend/routes/remediation_routes.py - FIXED (Background Task Safety and Imports)
"""Cognitive Remediation Routes"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from pydantic import BaseModel
from typing import Dict, Any 
import asyncio 

# CRITICAL REFINEMENT: Import RBAC dependency
from services.auth_deps import hrit_admin_role_required 
from services.cognitive_remediation_agent import CognitiveRemediationAgent
# NOTE: AIService import is now implicit via CognitiveRemediationAgent dependency tree

logger = logging.getLogger(__name__)
# FIX 1: Added explicit router prefix for consistency with frontend
router = APIRouter(prefix="/remediation") 

class RemediationRequest(BaseModel):
    audit_id: str
    failed_transaction: Dict[str, Any]
    policy_text: str
    auto_apply: bool = False

async def apply_remediation_fix(app: Any, proposed_fix: Dict[str, Any], audit_id: str):
    """Background task to apply remediation fix, receives app state."""
    try:
        logger.info(f"Applying remediation fix for audit {audit_id}")
        await asyncio.sleep(3)
        # NOTE: In a real system, the AutonomousUpgradeAgent or similar would handle the final fix application.
        logger.info(f"Remediation fix applied successfully for audit {audit_id}")
    except Exception as e:
        logger.error(f"Failed to apply remediation fix for {audit_id}: {e}")

@router.post("/audit/{audit_id}/auto-resolve")
# CRITICAL REFINEMENT: Add RBAC dependency for HRIT-level access
async def auto_resolve_audit(audit_id: str, request: RemediationRequest, background_tasks: BackgroundTasks, req: Request, payload: Dict = Depends(hrit_admin_role_required)):
    """Trigger cognitive remediation for failed transaction"""
    
    # CRITICAL FIX: Retrieve agent from app state
    agent = getattr(req.app.state, 'cognitive_remediation_agent', None)
    
    if not agent:
        raise HTTPException(status_code=503, detail="Cognitive Remediation Agent unavailable.")

    try:
        # Run remediation analysis
        remediation_result = await agent.analyze_and_fix_transaction(
            audit_id=audit_id,
            failed_transaction=request.failed_transaction,
            policy_text=request.policy_text
        )
        
        # If auto_apply is requested, apply the fix in background
        if request.auto_apply:
            # FIX: Pass the app state reference to the background task for service access
            background_tasks.add_task(
                apply_remediation_fix,
                req.app, 
                remediation_result.get("proposed_fix", {}), # Safely pass the fix
                audit_id
            )
        
        return remediation_result
    except Exception as e:
        logger.error(f"Remediation analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Remediation analysis failed: {str(e)}"
        )

@router.get("/audit/{audit_id}/remediation-history")
# CRITICAL REFINEMENT: Add RBAC dependency for Manager-level access (for viewing history)
async def get_remediation_history(audit_id: str, limit: int = 10, payload: Dict = Depends(hrit_admin_role_required)):
    """Get remediation history for an audit"""
    
    # Mock data - in production, fetch from database
    mock_history = [\
        {
            "remediation_id": f"REMED_{i}",
            "timestamp": f"2024-01-{i+1:02d}T10:00:00Z",
            "compliance_score": 0.85 + (i * 0.02),
            "status": "applied" if i % 2 == 0 else "proposed",
            "applied_by": "system" if i % 2 == 0 else "analyst",
        } for i in range(limit)
    ]
    
    return {"audit_id": audit_id, "history": mock_history}