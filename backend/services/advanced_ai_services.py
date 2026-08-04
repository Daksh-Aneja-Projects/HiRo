# backend/services/advanced_ai_services.py
# /backend/services/advanced_ai_services.py
# backend services/advanced_ai_services.py
"""Advanced AI Services - Production-ready
All flows use live DB lookups and deterministic logic."""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import secrets
import logging
from pydantic import BaseModel, Field, ConfigDict
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
DEFAULT_DB_NAME = settings.MONGO_DB_NAME if hasattr(settings, 'MONGO_DB_NAME') else "ahcm_db"
TIMESHEET_HISTORICAL_WEEKS = settings.TIMESHEET_HISTORICAL_WEEKS if hasattr(settings, 'TIMESHEET_HISTORICAL_WEEKS') else 12
TIMESHEET_MAX_HOURS_OVERTIME_RISK = settings.TIMESHEET_MAX_HOURS_OVERTIME_RISK if hasattr(settings, 'TIMESHEET_MAX_HOURS_OVERTIME_RISK') else 60
TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD = settings.TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD if hasattr(settings, 'TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD') else 0.2
TIMESHEET_HISTORICAL_DEVIATION_THRESHOLD = settings.TIMESHEET_HISTORICAL_DEVIATION_THRESHOLD if hasattr(settings, 'TIMESHEET_HISTORICAL_DEVIATION_THRESHOLD') else 0.3
TIMESHEET_AUTO_APPROVE_SCORE = settings.TIMESHEET_AUTO_APPROVE_SCORE if hasattr(settings, 'TIMESHEET_AUTO_APPROVE_SCORE') else 0.75
TIMESHEET_REVIEW_REQUIRED_SCORE = settings.TIMESHEET_REVIEW_REQUIRED_SCORE if hasattr(settings, 'TIMESHEET_REVIEW_REQUIRED_SCORE') else 0.4
TIMESHEET_SCHEDULE_MATCH_WEIGHT = settings.TIMESHEET_SCHEDULE_MATCH_WEIGHT if hasattr(settings, 'TIMESHEET_SCHEDULE_MATCH_WEIGHT') else 0.30
TIMESHEET_OVERTIME_WEIGHT = settings.TIMESHEET_OVERTIME_WEIGHT if hasattr(settings, 'TIMESHEET_OVERTIME_WEIGHT') else 0.40
TIMESHEET_HISTORICAL_WEIGHT = settings.TIMESHEET_HISTORICAL_WEIGHT if hasattr(settings, 'TIMESHEET_HISTORICAL_WEIGHT') else 0.30

class FlexiCompSimulation(BaseModel):
    model_config = ConfigDict(protected_namespaces=()) 
    valid: bool
    total_allocated: float
    budget_remaining: float
    message: str
    proposed_plan: Dict[str, Any]

class TimesheetReconResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=()) 
    timesheet_id: str
    ml_confidence_score: float = Field(..., ge=0.0, le=1.0)
    reconciliation_status: str
    anomalies: List[Dict[str, Any]]
    auto_approved: bool

class AdvancedAIServices:
    """Advanced AI services that operate against live DB collections."""
    def __init__(self, mongo_client: AsyncIOMotorClient):
        self.db = mongo_client[DEFAULT_DB_NAME]
        self.users = self.db.users 
        self.flexi_comp = self.db.flexi_comp_plans
        self.timesheets = self.db.timesheets

    async def simulate_flexi_comp(self, user_id: str, plan_changes: Dict[str, Any]) -> FlexiCompSimulation:
        """
        Fetch the user's current flexi-comp plan and apply changes using deterministic budget check."""
        current_plan = await self.flexi_comp.find_one({"user_id": user_id})
        
        if current_plan:
            current_plan.pop("_id", None)
        else:
            emp = await self.users.find_one({"username": user_id.lower()})
            
            default_budget = float(emp.get("flexi_budget", 100000.0)) if emp else 100000.0
            default_salary = float(emp.get("base_salary", 60000.0)) if emp else 60000.0
            
            current_plan = {
                "user_id": user_id,
                "total_budget": default_budget,
                "base_salary": default_salary,
                "health_insurance": 0.0,
                "retirement_401k": 0.0,
                "stock_options": 0.0,
                "wellness_budget": 0.0,
                "learning_budget": 0.0
            }

        proposed_plan = dict(current_plan)
        
        for k, v in plan_changes.items():
            if k in proposed_plan:
                try:
                    proposed_plan[k] = float(v)
                except (ValueError, TypeError):
                    proposed_plan[k] = v
        
        total_budget = float(proposed_plan.get("total_budget", 0))
        EXCLUDED_KEYS = {"user_id", "total_budget", "base_salary", "plan_id", "applied_at"}
        total_allocated = sum(
            float(proposed_plan[k])
            for k in proposed_plan.keys()
            if k not in EXCLUDED_KEYS and isinstance(proposed_plan.get(k), (int, float, str)) and self._is_valid_float(proposed_plan[k])
        )
        
        valid = total_allocated <= total_budget
        budget_remaining = total_budget - total_allocated
        message = ("Plan valid" if valid else f"Plan exceeds budget by ${abs(budget_remaining):.2f}")
        
        return FlexiCompSimulation(valid=valid, total_allocated=total_allocated, budget_remaining=budget_remaining, message=message, proposed_plan=proposed_plan)

    def _is_valid_float(self, value: Union[int, float, str]) -> bool:
        """Helper to check if a value is a valid float."""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    async def apply_flexi_comp(self, user_id: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a validated flexi-comp plan into the DB."""
        doc = dict(plan)
        doc["user_id"] = user_id
        doc["applied_at"] = datetime.now(timezone.utc).isoformat()
        if "plan_id" not in doc:
            doc["plan_id"] = f"FLEXI_{secrets.token_hex(8).upper()}"
        
        await self.flexi_comp.update_one({"user_id": user_id}, {"$set": doc}, upsert=True)
        return {"message": "Flexi-comp applied", "plan_id": doc["plan_id"]}

    async def ml_reconcile_timesheet(self, timesheet_id: str, user_id: str, submitted_hours: float, scheduled_hours: float, overtime_flag: bool) -> TimesheetReconResult:
        """
        Deterministic reconciliation using heuristics (Hyper-Specialized WFM Agent logic).
        Weights sum to 1.0 (Schedule: 0.30, Overtime: 0.40, Historical: 0.30)."""
        submitted = float(submitted_hours or 0.0)
        scheduled = float(scheduled_hours or 0.0)
        score = 0.0
        anomalies: List[Dict[str, Any]] = []

        # 1. Schedule match (Max weight: 0.30)
        if scheduled > 0:
            ratio = submitted / scheduled
            match_score = min(TIMESHEET_SCHEDULE_MATCH_WEIGHT, TIMESHEET_SCHEDULE_MATCH_WEIGHT * (1 - abs(1 - ratio)))
            score += match_score
            
            if abs(submitted - scheduled) / scheduled > TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD:
                anomalies.append({"type": "schedule_mismatch", "desc": f"Deviation >{TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD*100}% from scheduled"})
        elif submitted > 0:
            # Submitted hours but none scheduled - partial match
            score += TIMESHEET_SCHEDULE_MATCH_WEIGHT * 0.5
        else:
            # Submitted 0, Scheduled 0 (Idle week) - full match score
            score += TIMESHEET_SCHEDULE_MATCH_WEIGHT * 1.0
            
        # 2. Overtime (Max weight: 0.40)
        if submitted > TIMESHEET_MAX_HOURS_OVERTIME_RISK:
            anomalies.append({"type": "excessive_overtime", "desc": f"Submitted > {TIMESHEET_MAX_HOURS_OVERTIME_RISK}h"})
            score += TIMESHEET_OVERTIME_WEIGHT * 0.1
        elif overtime_flag:
            score += TIMESHEET_OVERTIME_WEIGHT * 0.8
        else:
            score += TIMESHEET_OVERTIME_WEIGHT
            
        # 3. Historical variance (Max weight: 0.30)
        if user_id:
            hist = await self.timesheets.find({"user_id": user_id.lower()}).sort("submitted_at", -1).limit(TIMESHEET_HISTORICAL_WEEKS).to_list(length=None)
            
            hours = [float(h.get("total_hours", 0.0)) for h in hist if h.get("total_hours") is not None]
            
            if hours:
                hist_avg = sum(hours) / len(hours)
                deviation = abs(submitted - hist_avg) / max(1.0, hist_avg)
                
                if deviation > TIMESHEET_HISTORICAL_DEVIATION_THRESHOLD:
                    anomalies.append({"type": "historical_deviation", "detail": f"{deviation:.2f} deviation"})
                    score += TIMESHEET_HISTORICAL_WEIGHT * 0.1
                else:
                    score += TIMESHEET_HISTORICAL_WEIGHT
            else:
                score += TIMESHEET_HISTORICAL_WEIGHT * 0.5
        
        final = max(0.0, min(1.0, score))
        
        status = "approved" if final >= TIMESHEET_AUTO_APPROVE_SCORE else ("review_required" if final >= TIMESHEET_REVIEW_REQUIRED_SCORE else "denied")
        auto_approved = status == "approved"
        
        return TimesheetReconResult(timesheet_id=timesheet_id, ml_confidence_score=round(final, 3), reconciliation_status=status, anomalies=anomalies, auto_approved=auto_approved)

class MockAsyncIOMotorClient:
    def __init__(self): pass
    def __getitem__(self, name): return self
    def __getattr__(self, name): return self
    def get_default_database(self): return self
    async def find_one(self, *args, **kwargs): return None
    async def update_one(self, *args, **kwargs): return None
    def find(self, *args, **kwargs): return self
    def sort(self, *args, **kwargs): return self
    def limit(self, *args, **kwargs): return self
    async def to_list(self, length): return []

if __name__ == "__main__":
    advanced_ai_services = AdvancedAIServices(mongo_client=MockAsyncIOMotorClient())