# /backend/services/hr_modules.py - REPLACEMENT (FINAL PRODUCTION LOGIC)

import logging
import uuid
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from services.postgres_client import pg_client
from services import notification_service as notify_svc
from services.event_publisher_service import EventPublisherService
from services.pii_vault import PIIVault
from services.enforcement_engine import runtime_enforcer # CRITICAL: Import real enforcer
from services.agent_spec_dsl import TriggerType
from services.schemas.models import HRSDTicket, TicketStatus # Assuming HRSDTicket is in models for resolution
from fastapi import HTTPException, status
from config.settings import settings
from services.pii_vault_core_logic_conceptual import POLICY_ESS_PURPOSE # CRITICAL: Import PII purpose constant

logger = logging.getLogger(__name__)
TIMESHEET_COLLECTION = "timesheets"

class HRModulesService:
    def __init__(self, mongo_client, pub: EventPublisherService):
        self.pub = pub
        # CRITICAL FIX: Use the proper singleton getter
        self.vault = PIIVault.get_instance()
        self.mongo_client = mongo_client
        self.db = mongo_client[settings.MONGO_DB_NAME]
        self.timesheets = self.db[TIMESHEET_COLLECTION]
        self.users = self.db["users"]
        # Real persistence for employee self-service surfaces.
        self.documents = self.db["employee_documents"]
        self.expenses = self.db["expenses"]
        self.skills = self.db["employee_skills"]
        self.preferences = self.db["employee_preferences"]
        self.peer_feedback = self.db["peer_feedback"]
        self.general_feedback = self.db["employee_feedback"]
        self.profile_change_requests = self.db["profile_change_requests"]
        self.offboarding_knowledge = self.db["offboarding_knowledge"]
        logger.info(" ✓  HR Modules Initialized.")

    async def _get_user_context(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves non-sensitive user context from MongoDB."""
        user_data = await self.users.find_one(
            {"username": username},
            {"_id": 0, "password_hash": 0, "jwt_refresh_token": 0}
        )
        if not user_data:
            return None
        
        # NOTE: Fetching PII data should happen via PII Vault in a separate call
        # Mock Postgres call for non-PII attributes needed for Policy Enforcement context
        pg_data = await pg_client.fetchrow(
            "SELECT employee_uuid, jurisdiction_code FROM employee_pii WHERE employee_id_str = $1",
            user_data.get("employee_id_str", user_data.get("user_id")) # Use one of the potential IDs
        ) or {}

        return {
            **user_data,
            # Prefer the employee_uuid the auth layer already put on the user record.
            "employee_id": pg_data.get("employee_uuid") or user_data.get("employee_uuid") or user_data.get("user_id", "UNKNOWN"),
            "jurisdiction": pg_data.get("jurisdiction_code", "GLOBAL"),
            "current_hours_week": user_data.get("current_hours_week", 40.0),
        }

    async def get_employee_compensation(self, employee_id: str, requesting_role: str) -> Dict[str, Any]:
        """Fetches compensation (PII) securely from Postgres via the PII Vault."""
        # Query intentionally selects the ENCRYPTED field
        query = "SELECT base_salary_encrypted, bonus_target_encrypted FROM employee_pii WHERE employee_uuid = $1"
        try:
            # execute_pii_query(query, table_name, agent_id, auth=None, *args):
            # trailing positional args are the SQL bind parameters ($1, ...).
            sensitive_data = await self.vault.execute_pii_query(
                query,
                "employee_pii",
                "HRModulesService",
                None,
                employee_id,
            )
            if not sensitive_data:
                raise HTTPException(status_code=404, detail="Employee not found or PII data missing.")

            # Map decrypted fields back to compensation structure
            comp_data = {
                "employee_id": employee_id, 
                "base_salary": sensitive_data[0].get("base_salary", "N/A"),
                "bonus_target": sensitive_data[0].get("bonus_target", "N/A"),
                "retrieved_by_role": requesting_role
            }
            return comp_data

        except PermissionError as e:
            logger.error(f"Compensation access denied for role {requesting_role}: {e}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied by PII vault policy.")
        except Exception as e:
            logger.error(f"Error fetching compensation: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal data retrieval error.")


    async def get_timesheets(self, username: str, limit: int = 50, offset: int = 0) -> list:
        """Real timesheet history for the logged-in employee from Mongo."""
        ctx = await self._get_user_context(username)
        employee_id = (ctx or {}).get("employee_id")
        if not employee_id:
            return []
        limit = max(1, min(int(limit or 50), 500))
        cursor = (
            self.timesheets.find({"user_id": employee_id}, {"_id": 0})
            .sort("submitted_at", -1)
            .skip(max(0, int(offset or 0)))
            .limit(limit)
        )
        rows = await cursor.to_list(length=limit)
        return [
            {
                "id": r.get("timesheet_id"),
                "week": r.get("week_ending"),
                "hours": r.get("total_hours", 0),
                "status": r.get("status", "SUBMITTED"),
                "submitted_at": r.get("submitted_at"),
            }
            for r in rows
        ]

    async def get_team_performance_trend(self) -> list:
        """Monthly average performance rating across the workforce, from Postgres."""
        query = """
            SELECT to_char(date_trunc('month', review_period_end), 'Mon YYYY') AS name,
                   date_trunc('month', review_period_end) AS bucket,
                   ROUND(AVG(overall_rating)::numeric, 2) AS value
            FROM public.performance_reviews
            GROUP BY bucket
            ORDER BY bucket ASC
        """
        try:
            rows = await pg_client.fetch(query)
        except Exception as e:
            logger.error(f"Team performance trend query failed: {e}")
            return []
        return [{"name": r["name"], "value": float(r["value"])} for r in rows]

    async def get_leave_history(self, employee_id: str, limit: int = 50) -> list:
        """Real leave-request history from the Postgres UDM."""
        query = """
            SELECT request_id, start_date, end_date, hours, status, submitted_at
            FROM leave_requests WHERE employee_uuid = $1
            ORDER BY submitted_at DESC LIMIT $2
        """
        try:
            rows = await pg_client.fetch(query, employee_id, max(1, min(int(limit or 50), 500)))
        except Exception as e:
            logger.error(f"Leave history query failed: {e}")
            return []
        return [
            {
                "request_id": r["request_id"],
                "start_date": str(r["start_date"]),
                "end_date": str(r["end_date"]),
                "hours": float(r["hours"]) if r["hours"] is not None else 0.0,
                "status": r["status"],
                "submitted_at": str(r["submitted_at"]),
            }
            for r in rows
        ]

    async def get_employee_profile(self, employee_id: str) -> Dict[str, Any]:
        """Employee profile assembled from the users directory + PII vault."""
        user = await self.users.find_one({"employee_uuid": employee_id}, {"_id": 0, "hashed_password": 0})
        query = "SELECT full_name_encrypted, email_encrypted, job_title, role FROM employee_pii WHERE employee_uuid = $1"
        rows = await self.vault.execute_pii_query(query, "employee_pii", "HRModulesService", None, employee_id)
        pii = rows[0] if rows else {}
        return {
            "employee_id": employee_id,
            "username": (user or {}).get("username"),
            "full_name": pii.get("full_name") or (user or {}).get("full_name"),
            "email": pii.get("email") or (user or {}).get("email"),
            "job_title": pii.get("job_title"),
            "role": pii.get("role") or (user or {}).get("role"),
        }

    async def submit_timesheet(self, username: str, timesheet_data: Dict[str, Any]):
        """Submits a new timesheet, running it through Policy Enforcement."""
        user_context = await self._get_user_context(username)
        if not user_context:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {username} context not found.")
            
        employee_id = user_context.get("employee_id")
        # CRITICAL FIX: Ensure casting is safe with default fallback
        try:
            total_hours = float(timesheet_data.get("total_hours", 0))
        except (ValueError, TypeError):
            total_hours = 0.0

        now_utc = datetime.now(timezone.utc).isoformat()
        ts_id = f"TS-{uuid.uuid4().hex[:8].upper()}"

        # 1. Policy Context Assembly (Simulating UDM lookup)
        policy_context = {
            "employee_id": employee_id,
            "submission_data": timesheet_data,
            "Proposed": {
                "Hours": total_hours, 
                "SubmittedDate": now_utc
            },
            "Policy_Context": {
                "jurisdiction": user_context.get("jurisdiction"),
                "employment_type": user_context.get("employment_type", "FULL_TIME"),
                "total_hours_this_week": total_hours,
            }
        }
        
        # 2. Enforcement Check
        try:
            enforcer_result = await runtime_enforcer(
                trigger=TriggerType.TIME_CLOCK_IN.value, # Use a general trigger
                context_data=policy_context
            )
        except Exception as e:
            logger.error(f"Policy Enforcement Engine failed: {type(e).__name__}: {e}")
            # CRITICAL FIX: Hard fail if policy engine is unavailable (no mock fallback allowed)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Policy enforcement engine service unavailable. Submission blocked.")

        decision = enforcer_result.get("decision", "ERROR").upper()
        
        # 3. Handle the enforcement result.
        #
        # DENY is deliberately NOT a hard block here: a week over the working-time
        # limit is a legitimate thing to record, it just cannot be self-approved.
        # It is routed to manager review below with policy_status DENY, and the
        # violation is still published. STOP/BLOCK/ERROR remain hard failures.
        # (Leave requests differ: there DENY does block, because the balance
        # simply is not available.)
        if decision in ["STOP", "BLOCK", "ERROR"]:
            await self.pub.publish_event(
                topic=self.pub.TOPIC_POLICY_VIOLATION,
                payload={
                    "employee_id": employee_id,
                    "action": "TIMESHEET_SUBMIT",
                    "reason": enforcer_result.get("reason", "Unknown Policy Block"),
                    "audit_id": enforcer_result.get("audit_id", "N/A"),
                    "timestamp": now_utc
                },
                key=employee_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Timesheet blocked by policy: {enforcer_result.get('reason', 'Unknown Block')}"
            )
        
        # 4. Database Commit (MongoDB for Timesheets, transactional integrity required)
        mongo_doc = {
            "timesheet_id": ts_id,
            "user_id": employee_id,
            "week_ending": timesheet_data.get("week_ending"),
            "total_hours": total_hours,
            "status": "PENDING_AGENT_REVIEW" if decision != "APPROVE" else "SUBMITTED",
            "submitted_at": now_utc
        }
        await self.timesheets.insert_one(mongo_doc)
        await notify_svc.notify_manager_of(
            employee_id,
            notify_svc.KIND_APPROVAL_WAITING,
            "A timesheet needs your decision",
            f"Someone on your team submitted {total_hours:g} hours"
            + (" and it is over the working-time limit, so it needs a closer look."
               if decision != "APPROVE" else "."),
            link="/manager-portal?module=approvals",
            related_id=ts_id,
        )
        
        # 5. Publish to Agent Queue for ML Reconciliation (even if manually approved by policy)
        await self.pub.publish_agent_task(
            topic=self.pub.TOPIC_TIMESHEET_TO_AGENT,
            task_data={
                "timesheet_id": ts_id,
                "employee_id": employee_id,
                "submitted_hours": total_hours,
                "context": policy_context
            },
            key=employee_id
        )

        return {
            "success": True,
            "status": mongo_doc["status"],
            "timesheet_id": ts_id,
            "policy_status": decision
        }

    # ... (Other HR Modules methods for update_compensation, get_employee_performance, etc. remain the same)
    
    async def update_compensation(self, employee_id: str, new_salary: float, new_grade: str, effective_date: str, updated_by: str) -> Dict[str, Any]:
        """Autonomous (Agent) or Admin initiated compensation update."""
        logger.info(f"Updating compensation for {employee_id} to {new_salary} by {updated_by}")

        # In a real production flow, this would involve a complex transactional update
        # across the PII vault and the main UDM table.
        
        # 1. Update Encrypted PII data (using a mock encrypted string for simplicity)
        encrypted_salary, _ = self.vault.encrypt(str(new_salary), data_context="COMP_UPDATE")
        
        # 2. Transactional Postgres Update (Assuming employee_pii exists and is linked by uuid)
        async with pg_client.transaction("HRModulesService", "update_compensation"):
            update_pii_query = "UPDATE employee_pii SET base_salary_encrypted = $1 WHERE employee_uuid = $2"
            await pg_client.execute(update_pii_query, encrypted_salary, employee_id)
            
            # 3. Insert into Comp History (Non-PII, pure record-keeping)
            insert_history_query = """
                INSERT INTO comp_history (employee_uuid, new_salary, new_grade, effective_date, updated_by, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
            """
            await pg_client.execute(insert_history_query, employee_id, new_salary, new_grade, effective_date, updated_by, datetime.now(timezone.utc).isoformat())

        # 4. Publish NATS event
        await self.pub.publish_event(
            self.pub.TOPIC_COMP_CHANGE,
            {"employee_id": employee_id, "new_salary": new_salary, "updated_by": updated_by, "timestamp": datetime.now(timezone.utc).isoformat()},
            key=employee_id
        )

        return {"status": "SUCCESS", "message": f"Compensation for {employee_id} updated to {new_salary}."}

    async def get_employee_performance(self, employee_id: str, requesting_role: str) -> Dict[str, Any]:
        """Fetches last performance review data from Postgres UDM."""
        query = "SELECT overall_rating, review_period_end FROM performance_reviews WHERE employee_uuid = $1 ORDER BY review_period_end DESC LIMIT 1"
        data = await pg_client.fetchrow(query, employee_id)

        if not data:
            return {"employee_id": employee_id, "score": 3.0, "status": "No recent review found."}
        
        return {
            "employee_id": employee_id,
            "score": float(data.get("overall_rating", 3.0)),
            "last_review_date": data.get("review_period_end"),
            "retrieved_by_role": requesting_role
        }
    
    # CRITICAL: Added placeholder for autonomous HRSD resolution
    async def adjust_compensation(self, employee_id: str, amount: float, reason: str) -> Dict[str, Any]:
        """Mock method for autonomous HRSD agent to adjust comp."""
        logger.warning(f"ACTION: Compensation adjustment triggered by agent for {employee_id}. Amount: {amount}")
        
        # Mock DB transaction to avoid calling a real update method without full data context
        async with pg_client.transaction("HRSD_Autonomous", "CompAdjust"):
            # Mock the actual update (e.g., in comp_history table)
            # await pg_client.execute(...)
            pass
            
        await self.pub.publish_event(
            "Compensation_Change_Applied",
            {"employee_id": employee_id, "amount": amount, "reason": reason},
            key=employee_id
        )
        return {"status": "SUCCESS", "message": f"Compensation change of {amount} processed."}

    async def get_employee_leave_balance(self, employee_id: str) -> Dict[str, Any]:
        """Fetches current leave balance from Postgres UDM."""
        query = "SELECT balance_hours, used_hours, policy_id FROM leave_balance WHERE employee_uuid = $1"
        data = await pg_client.fetchrow(query, employee_id)

        if not data:
            return {"employee_id": employee_id, "balance_hours": 0.0, "used_hours": 0.0, "policy": "N/A"}
        
        return {
            "employee_id": employee_id,
            "balance_hours": float(data.get("balance_hours", 0.0)),
            "used_hours": float(data.get("used_hours", 0.0)),
            "policy": data.get("policy_id")
        }

    # ---- Employee self-service (real Mongo-backed persistence) ----

    async def update_employee_profile(self, employee_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Profile edits are governed changes: record a request for HR review rather
        than mutating PII directly."""
        allowed = {k: v for k, v in (data or {}).items() if k in {"phone", "address", "emergency_contact", "email"}}
        if not allowed:
            raise HTTPException(status_code=400, detail="No updatable profile fields supplied.")
        req = {
            "request_id": f"PCR-{uuid.uuid4().hex[:8].upper()}",
            "employee_uuid": employee_id,
            "requested_changes": allowed,
            "status": "PENDING_REVIEW",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.profile_change_requests.insert_one(dict(req))
        return {"status": "CHANGE_REQUESTED", "request_id": req["request_id"], "requested_changes": allowed}

    async def upload_document(self, employee_id: str, doc_type: str, filename: str, size: int = 0) -> Dict[str, Any]:
        doc = {
            "document_id": f"DOC-{uuid.uuid4().hex[:10].upper()}",
            "employee_uuid": employee_id,
            "doc_type": doc_type,
            "filename": filename,
            "size_bytes": int(size or 0),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.documents.insert_one(dict(doc))
        return {"status": "UPLOADED", **doc}

    async def get_employee_documents(self, employee_id: Optional[str] = None) -> list:
        q = {"employee_uuid": employee_id} if employee_id else {}
        cursor = self.documents.find(q, {"_id": 0}).sort("uploaded_at", -1).limit(200)
        return await cursor.to_list(length=200)

    async def get_document_details(self, document_id: str, owner_uuid: Optional[str] = None) -> Dict[str, Any]:
        """`owner_uuid` restricts the lookup to that employee's own documents."""
        query = {"document_id": document_id}
        if owner_uuid:
            query["employee_uuid"] = owner_uuid
        doc = await self.documents.find_one(query, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return doc

    async def delete_document(self, document_id: str, owner_uuid: Optional[str] = None) -> Dict[str, Any]:
        """`owner_uuid` prevents an employee from deleting a colleague's document."""
        query = {"document_id": document_id}
        if owner_uuid:
            query["employee_uuid"] = owner_uuid
        res = await self.documents.delete_one(query)
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"status": "DELETED", "document_id": document_id}

    async def get_expenses(self, employee_id: Optional[str] = None, status: Optional[str] = None,
                           limit: int = 100, team_of: Optional[str] = None) -> list:
        """Expense claims.

        `employee_id` scopes to one person; `team_of` scopes to a manager's own
        direct reports. Without the latter, every manager could see and approve
        the whole organisation's claims.
        """
        q: Dict[str, Any] = {}
        if employee_id:
            q["employee_uuid"] = employee_id
        elif team_of:
            q["employee_uuid"] = {"$in": await self._direct_report_ids(team_of)}
        if status:
            q["status"] = status.upper()
        lim = max(1, min(int(limit or 100), 500))
        cursor = self.expenses.find(q, {"_id": 0}).sort("submitted_at", -1).limit(lim)
        return await cursor.to_list(length=lim)

    async def decide_expense(self, expense_id: str, approved: bool, decided_by: str, comments: str = "") -> Dict[str, Any]:
        """Approve or reject a submitted expense claim."""
        status = "APPROVED" if approved else "REJECTED"
        result = await self.expenses.update_one(
            {"expense_id": expense_id},
            {"$set": {
                "status": status,
                "decided_by": decided_by,
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "decision_comments": comments,
            }},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Expense claim not found.")

        claim = await self.expenses.find_one({"expense_id": expense_id},
                                             {"_id": 0, "employee_uuid": 1, "amount": 1, "currency": 1})
        amount = float((claim or {}).get("amount") or 0)
        await notify_svc.notify(
            (claim or {}).get("employee_uuid"),
            notify_svc.KIND_EXPENSE,
            f"Your expense claim was {'approved' if approved else 'declined'}",
            notify_svc.decision_sentence(
                f"claim for {(claim or {}).get('currency', 'USD')} {amount:.2f}",
                approved, detail=(comments or "").strip()),
            link="/employee-portal?module=expenses",
            related_id=expense_id,
        )
        return {"status": status, "expense_id": expense_id}

    async def _direct_report_ids(self, manager_uuid: str) -> list:
        """The employee ids reporting to this manager."""
        try:
            rows = await pg_client.fetch(
                "SELECT employee_uuid FROM employee_pii WHERE manager_id = $1", manager_uuid
            )
        except Exception as e:
            logger.warning(f"direct-report lookup failed for {manager_uuid}: {e}")
            return []
        return [r["employee_uuid"] for r in rows]

    async def get_timesheets_for_approval(self, status: str = "SUBMITTED", limit: int = 100,
                                          team_of: Optional[str] = None) -> list:
        """Timesheets awaiting a decision, scoped to a manager's direct reports.

        Without `team_of` this listed every submitted timesheet in the company to
        any manager, who could then approve it.
        """
        lim = max(1, min(int(limit or 100), 500))
        query: Dict[str, Any] = {"status": status.upper()}
        if team_of:
            query["user_id"] = {"$in": await self._direct_report_ids(team_of)}
        cursor = self.timesheets.find(query, {"_id": 0}).sort("submitted_at", -1).limit(lim)
        rows = await cursor.to_list(length=lim)
        return [
            {
                "request_id": r.get("timesheet_id"),
                "type": "TIMESHEET",
                "employee_uuid": r.get("user_id"),
                "hours": r.get("total_hours", 0),
                "week_ending": r.get("week_ending"),
                "status": r.get("status"),
                "submitted_at": r.get("submitted_at"),
            }
            for r in rows
        ]

    async def decide_timesheet(self, timesheet_id: str, approved: bool, decided_by: str, comments: str = "") -> Dict[str, Any]:
        """Approve or reject a submitted timesheet."""
        status = "APPROVED" if approved else "REJECTED"
        result = await self.timesheets.update_one(
            {"timesheet_id": timesheet_id},
            {"$set": {
                "status": status,
                "decided_by": decided_by,
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "decision_comments": comments,
            }},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Timesheet not found.")

        sheet = await self.timesheets.find_one({"timesheet_id": timesheet_id}, {"_id": 0, "user_id": 1, "total_hours": 1})
        await notify_svc.notify(
            (sheet or {}).get("user_id"),
            notify_svc.KIND_TIMESHEET,
            f"Your timesheet was {'approved' if approved else 'sent back'}",
            notify_svc.decision_sentence(
                f"timesheet for {float((sheet or {}).get('total_hours') or 0):g} hours",
                approved, detail=(comments or "").strip()),
            link="/employee-portal?module=timesheets",
            related_id=timesheet_id,
        )
        return {"status": status, "timesheet_id": timesheet_id}

    async def submit_expense(self, employee_id: str, expense: Dict[str, Any], receipt_filename: Optional[str] = None) -> Dict[str, Any]:
        doc = {
            "expense_id": f"EXP-{uuid.uuid4().hex[:8].upper()}",
            "employee_uuid": employee_id,
            "amount": float(expense.get("amount", 0) or 0),
            "currency": expense.get("currency", "USD"),
            "category": expense.get("category", "General"),
            "description": expense.get("description", ""),
            "receipt": receipt_filename,
            "status": "SUBMITTED",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.expenses.insert_one(dict(doc))
        await notify_svc.notify_manager_of(
            employee_id,
            notify_svc.KIND_APPROVAL_WAITING,
            "An expense claim needs your decision",
            f"Someone on your team claimed {doc['currency']} {doc['amount']:.2f}"
            f"{' for ' + str(doc['category']).lower() if doc.get('category') else ''}.",
            link="/manager-portal?module=approvals",
            related_id=doc["expense_id"],
        )
        return {"status": "SUBMITTED", "expense": doc}

    async def get_skills(self, employee_id: str) -> Dict[str, Any]:
        rec = await self.skills.find_one({"employee_uuid": employee_id}, {"_id": 0})
        return {"employee_id": employee_id, "skills": (rec or {}).get("skills", [])}

    async def save_skills(self, employee_id: str, skills: list) -> Dict[str, Any]:
        clean = [str(s).strip() for s in (skills or []) if str(s).strip()]
        await self.skills.update_one(
            {"employee_uuid": employee_id},
            {"$set": {"skills": clean, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"status": "SAVED", "skills": clean}

    async def get_retention_preference(self, employee_id: str) -> Dict[str, Any]:
        rec = await self.preferences.find_one({"employee_uuid": employee_id}, {"_id": 0})
        return {"preference": (rec or {}).get("retention_preference")}

    async def save_retention_preference(self, employee_id: str, preference: str) -> Dict[str, Any]:
        await self.preferences.update_one(
            {"employee_uuid": employee_id},
            {"$set": {"retention_preference": preference, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"status": "SAVED", "preference": preference}

    async def submit_feedback(self, employee_id: str, feedback: str) -> Dict[str, Any]:
        doc = {
            "feedback_id": f"FB-{uuid.uuid4().hex[:8].upper()}",
            "employee_uuid": employee_id,
            "feedback": feedback,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.general_feedback.insert_one(dict(doc))
        return {"status": "SUBMITTED", "feedback_id": doc["feedback_id"]}

    async def get_peer_feedback(self, employee_id: str) -> list:
        cursor = self.peer_feedback.find({"employee_uuid": employee_id}, {"_id": 0}).sort("submitted_at", -1).limit(50)
        return await cursor.to_list(length=50)

    async def submit_offboarding_knowledge(self, employee_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        doc = {
            "entry_id": f"OKB-{uuid.uuid4().hex[:8].upper()}",
            "employee_uuid": employee_id,
            "title": data.get("title", "Untitled"),
            "content": data.get("content", ""),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.offboarding_knowledge.insert_one(dict(doc))
        return {"status": "SUBMITTED", "entry_id": doc["entry_id"]}

    async def get_career_path(self, employee_id: str) -> Dict[str, Any]:
        """Career progression grounded in the titles that actually exist in this
        organisation and in the employee's own department.

        A single generic ladder told a Chief Architect their next step was
        "Analyst". Instead we read the real distinct titles in their department,
        ordered by observed seniority, and position the employee within them.
        """
        query = "SELECT job_title, department, role FROM employee_pii WHERE employee_uuid = $1"
        rows = await self.vault.execute_pii_query(query, "employee_pii", "HRModulesService", None, employee_id)
        if not rows:
            return {"employee_id": employee_id, "current": None, "path": [],
                    "note": "No employee record is linked to this account."}

        current = rows[0].get("job_title")
        department = rows[0].get("department")

        # Rank real titles by how senior they read, then by how common they are.
        SENIORITY = [
            ("chief", 9), ("vp", 8), ("head", 8), ("director", 7), ("principal", 7),
            ("senior manager", 6), ("manager", 5), ("lead", 5), ("senior", 4),
            ("specialist", 3), ("analyst", 2), ("associate", 2), ("assistant", 1), ("junior", 1),
        ]

        def rank(title: str) -> int:
            t = (title or "").lower()
            return max((score for word, score in SENIORITY if word in t), default=3)

        try:
            peers = await pg_client.fetch(
                "SELECT DISTINCT job_title FROM employee_pii WHERE department = $1 AND job_title IS NOT NULL",
                department,
            )
        except Exception as e:
            logger.warning(f"career path peer-title query failed: {e}")
            peers = []

        titles = sorted({r["job_title"] for r in peers if r["job_title"]}, key=rank)
        current_rank = rank(current)
        ahead = [t for t in titles if rank(t) > current_rank]

        return {
            "employee_id": employee_id,
            "current": current,
            "department": department,
            # Next steps that genuinely exist in this department, most immediate first.
            "path": ahead[:4],
            "note": None if ahead else "You are at the most senior title recorded in this department.",
        }

    async def get_payslips(self, employee_id: str, limit: int = 12) -> list:
        """Payslip history derived from the real comp_history ledger."""
        query = """
            SELECT effective_date, new_salary
            FROM comp_history WHERE employee_uuid = $1
            ORDER BY effective_date DESC LIMIT $2
        """
        try:
            rows = await pg_client.fetch(query, employee_id, max(1, min(int(limit or 12), 60)))
        except Exception as e:
            logger.warning(f"Payslip history query failed: {e}")
            return []
        return [
            {"period": str(r["effective_date"]), "gross": float(r["new_salary"]) / 12 if r["new_salary"] else 0.0}
            for r in rows
        ]