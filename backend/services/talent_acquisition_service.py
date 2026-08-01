# services/talent_acquisition_service.py
"""Talent Acquisition Service: Advanced Pipeline Risk Modeling and Simulation."""
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from services.event_publisher_service import EventPublisherService
from services.postgres_client import pg_client

logger = logging.getLogger(__name__)

class TalentAcquisitionService:
    def __init__(self, publisher: EventPublisherService):
        self.publisher = publisher
        logger.info(" ✓  TalentAcquisitionService Initialized (Advanced Scoring Engine).")

    async def get_talent_pool_snapshot(self, mongo_client=None, db_name: str = None) -> Dict[str, Any]:
        """Talent pools built from the real workforce and open requisitions.

        This used to return two hardcoded pools (Engineering: 420) while the
        actual workforce held thousands. Pool size and attrition pressure now
        come from the employee UDM; open requisitions come from the requisitions
        store. Time-to-close and acceptance rate are not tracked by HiRo, so
        they are reported as unavailable rather than invented.
        """
        pools: Dict[str, Any] = {}
        try:
            rows = await pg_client.fetch(
                """SELECT department,
                          COUNT(*)                                AS size,
                          ROUND(AVG(dtla_risk_score)::numeric, 3) AS avg_risk,
                          ROUND(AVG(tenure_months))               AS avg_tenure
                     FROM public.employee_pii
                    WHERE department IS NOT NULL AND department <> ''
                    GROUP BY department
                    ORDER BY size DESC"""
            )
        except Exception as e:
            logger.error(f"Talent snapshot query failed: {e}")
            rows = []

        # Open requisitions per department, when the store is reachable.
        open_reqs: Dict[str, int] = {}
        if mongo_client is not None and db_name:
            try:
                cursor = mongo_client[db_name]["requisitions"].aggregate([
                    {"$match": {"status": "OPEN"}},
                    {"$group": {"_id": "$department", "n": {"$sum": 1}}},
                ])
                async for r in cursor:
                    open_reqs[r["_id"] or "Unknown"] = int(r["n"])
            except Exception as e:
                logger.warning(f"Open requisition count unavailable: {e}")

        for r in rows:
            dept = r["department"]
            pools[dept] = {
                "size": int(r["size"] or 0),
                "attrition_pressure": float(r["avg_risk"] or 0.0),
                "average_tenure_months": int(r["avg_tenure"] or 0),
                "open_reqs": open_reqs.get(dept, 0),
                "ttc_days": None,
                "acceptance_rate": None,
            }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pools": pools,
            "unavailable": ["ttc_days", "acceptance_rate"],
            "note": "Time to close and offer acceptance are tracked in the ATS, not in HiRo.",
        }

    # HiRo does not track time-to-close or offer acceptance -- those live in the
    # ATS. These are industry defaults, not measurements, and any response that
    # depends on them has to say so (see assumed_inputs()).
    INDUSTRY_BASELINE_TTC_DAYS = 60
    INDUSTRY_BASELINE_ACCEPTANCE_RATE = 0.8

    @classmethod
    def assumed_inputs(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """Which simulation inputs were industry defaults rather than measured.

        The snapshot already reports what it could not measure; this turns that
        into the plain-English wording a response carries alongside a risk score,
        so nobody reads an assumption as a reading off their own pipeline.
        """
        unavailable = list(state.get("unavailable") or [])
        labels = {"ttc_days": f"time to close ({cls.INDUSTRY_BASELINE_TTC_DAYS} days)",
                  "acceptance_rate": f"offer acceptance rate ({cls.INDUSTRY_BASELINE_ACCEPTANCE_RATE:.0%})"}
        assumed = [labels[u] for u in unavailable if u in labels]
        return {
            "baselines_are_industry_defaults": bool(assumed),
            "assumed_inputs": unavailable,
            "assumptions_note": (
                "Industry defaults were used for " + " and ".join(assumed) +
                " because HiRo does not track them; these are not measured from your pipeline."
            ) if assumed else "All simulation inputs were measured from your own pipeline.",
        }

    async def simulate_talent_scenario(self, scenario: Dict[str, Any], state: Dict[str, Any]) -> float:
        """ 
        Calculates TA Risk based on Time-to-Commit (TTC), Offer Acceptance Rate (OAR), and Open Requisitions.
        Algorithm: Risk = (TTC / 120) * 0.4 + (1 - OAR) * 0.4 + (OpenReqs / 50) * 0.2
        """
        # The snapshot returns pools under "pools"; reading "talent_pools" meant
        # this always fell back to defaults and ignored the real state.
        pools = state.get('pools') or state.get('talent_pools') or {}
        target = scenario.get('department') or 'Engineering'
        pool = pools.get(target) or next(iter(pools.values()), {})

        # Time-to-close and acceptance rate are not tracked by HiRo; the industry
        # baselines below are used only when the pool has no figure, and the
        # caller is told which inputs were assumed via `assumed_inputs()`.
        base_ttc = pool.get('ttc_days') or self.INDUSTRY_BASELINE_TTC_DAYS
        base_oar = pool.get('acceptance_rate') or self.INDUSTRY_BASELINE_ACCEPTANCE_RATE
        base_open_reqs = pool.get('open_reqs', 0)

        # 2. Apply Scenario Modifiers
        scenario_text = scenario.get('scenario_description', '').lower()
        ttc_modifier = 0
        oar_modifier = 0.0
        req_modifier = 0 # Modifier for open reqs

        if "competition" in scenario_text or "poaching" in scenario_text:
            ttc_modifier = 45 # Takes 45 days longer
            oar_modifier = -0.20 # 20% fewer accepts
            req_modifier = 5 # Need 5 more reqs open to match demand
        elif "reputation" in scenario_text:
            oar_modifier = -0.40
        elif "hiring freeze" in scenario_text:
            req_modifier = -5 # Reduces open reqs
            ttc_modifier = 10 # Longer TTC due to internal friction

        # 3. Calculate Final Scores
        final_ttc = base_ttc + ttc_modifier
        final_oar = max(0.0, base_oar + oar_modifier)
        final_reqs = max(0, base_open_reqs + req_modifier)

        # 4. Normalize Risk (Weights sum to 1.0)
        # TTC Risk: 120 days is 100% risk for this factor (Weight 0.4)
        ttc_risk_score = min(1.0, final_ttc / 120.0) * 0.4
        
        # OAR Risk: Lower acceptance = Higher risk (Weight 0.4)
        oar_risk_score = (1.0 - final_oar) * 0.4 
        
        # Open Reqs Risk: 50 open reqs is considered high risk (Weight 0.2)
        req_risk_score = min(1.0, final_reqs / 50.0) * 0.2
        
        # Weighted Total
        total_risk = ttc_risk_score + oar_risk_score + req_risk_score

        return max(0.0, min(1.0, total_risk))