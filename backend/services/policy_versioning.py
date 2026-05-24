# /backend/services/policy_versioning.py - MODIFIED for Rollback Transaction

import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union 
from datetime import datetime, timezone 
from dataclasses import dataclass, asdict, field 
from enum import Enum
from copy import deepcopy
import uuid 
import asyncio
# CRITICAL FIX: Import pg_client for transactional updates
from services.postgres_client import pg_client as local_pg_client # Renamed for clarity in this file

# --- Configuration Constants ---
DEFAULT_VERSION_NUMBER = "1.0.0"
VERSION_SEPARATOR = "."
DEFAULT_CHANGE_TYPE = "patch"

class PolicyStatus(str, Enum):
    """Policy lifecycle statuses"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

class ApprovalStatus(str, Enum):
    """Approval workflow statuses"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"

@dataclass
class PolicyVersion:
    """Individual policy version"""
    version_id: str
    policy_id: str
    version_number: str
    status: PolicyStatus
    content: Dict[str, Any]
    content_hash: str
    created_by: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    activated_at: Optional[str] = None
    deprecated_at: Optional[str] = None
    changelog: str = ""
    parent_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ApprovalRequest:
    """Policy approval request"""
    request_id: str
    version_id: str
    requested_by: str
    approvers: List[str] 
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    comments: List[Dict[str, Any]] = field(default_factory=list)
    resolved_at: Optional[str] = None

@dataclass
class PolicyAuditEntry:
    """Audit trail entry for policy changes"""
    audit_id: str
    version_id: str
    action: str 
    performed_by: str
    performed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class PolicyVersioningService:
    """Manages policy versions, approvals, and lifecycle (Synchronous Core Logic)"""
    def __init__(self):
        self.versions: Dict[str, PolicyVersion] = {}
        self.policy_index: Dict[str, List[str]] = {}
        self.active_versions: Dict[str, str] = {}
        self.approval_requests: Dict[str, ApprovalRequest] = {}
        self.audit_trail: List[PolicyAuditEntry] = []

    def _generate_content_hash(self, content: Dict[str, Any]) -> str:
        """
        Generate hash of policy content for integrity verification
        """
        content_str = json.dumps(deepcopy(content), sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def _increment_version(self, current_version: str, change_type: str = DEFAULT_CHANGE_TYPE) -> str:
        """
        Increment version number (semantic versioning)
        """
        parts = current_version.split(VERSION_SEPARATOR)
        parts = parts + ["0"] * (3 - len(parts))
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return DEFAULT_VERSION_NUMBER
            
        if change_type == "major":
            return f"{major + 1}.0.0"
        elif change_type == "minor":
            return f"{major}.{minor + 1}.0"
        else:
            return f"{major}.{minor}.{patch + 1}"

    def create_policy_version(self,
                              policy_id: str,
                              content: Dict[str, Any],
                              created_by: str,
                              changelog: str = "",
                              parent_version_id: Optional[str] = None) -> PolicyVersion:
        """
        Create new policy version
        """
        current_active_version = self.get_active_version(policy_id)
        
        # CRITICAL FIX: Use explicit version logic
        if parent_version_id and parent_version_id in self.versions:
            parent_version = self.versions[parent_version_id]
            version_number = self._increment_version(parent_version.version_number, DEFAULT_CHANGE_TYPE)
        elif current_active_version:
            version_number = self._increment_version(current_active_version.version_number, DEFAULT_CHANGE_TYPE)
            parent_version_id = current_active_version.version_id
        else:
            version_number = DEFAULT_VERSION_NUMBER
            parent_version_id = None
            
        version_id = f"{policy_id}_v{version_number.replace(VERSION_SEPARATOR, '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        version = PolicyVersion(
            version_id=version_id,
            policy_id=policy_id,
            version_number=version_number,
            status=PolicyStatus.DRAFT,
            content=deepcopy(content),
            content_hash=self._generate_content_hash(content),
            created_by=created_by,
            changelog=changelog,
            parent_version=parent_version_id,
            # created_at is handled by default_factory
        )
        self.versions[version_id] = version
        if policy_id not in self.policy_index:
            self.policy_index[policy_id] = []
        self.policy_index[policy_id].append(version_id)
        
        self._add_audit_entry(
            version_id=version_id,
            action="created",
            performed_by=created_by,
            details={"changelog": changelog, "version_number": version_number}
        )
        return version

    def update_version_content(self,
                               version_id: str,
                               updated_content: Dict[str, Any],
                               updated_by: str,
                               changelog: str = "") -> PolicyVersion:
        """
        Update content of a draft version
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
        
        version = self.versions[version_id]
        if version.status != PolicyStatus.DRAFT:
            raise ValueError(f"Cannot update version with status {version.status.value}. Only DRAFT versions can be updated.")
            
        version.content = deepcopy(updated_content)
        version.content_hash = self._generate_content_hash(updated_content)
        version.changelog += f"\n{datetime.now(timezone.utc).isoformat()}: {changelog}"
        
        self._add_audit_entry(
            version_id=version_id,
            action="updated",
            performed_by=updated_by,
            details={"changelog": changelog}
        )
        return version

    def submit_for_approval(self,
                            version_id: str,
                            requested_by: str,
                            approvers: List[str],
                            comments: str = "") -> ApprovalRequest:
        """
        Submit policy version for approval
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
            
        version = self.versions[version_id]
        if version.status != PolicyStatus.DRAFT:
            raise ValueError(f"Only DRAFT versions can be submitted for approval")
            
        version.status = PolicyStatus.REVIEW
        request_id = f"APPROVAL_{uuid.uuid4().hex[:8].upper()}"
        current_time = datetime.now(timezone.utc).isoformat()
        
        approval_request = ApprovalRequest(
            request_id=request_id,
            version_id=version_id,
            requested_by=requested_by,
            approvers=approvers,
            status=ApprovalStatus.PENDING,
            # requested_at is handled by default_factory
        )
        
        if comments:
            approval_request.comments.append({
                "user": requested_by,
                "timestamp": current_time,
                "comment": comments
            })
        self.approval_requests[request_id] = approval_request
        
        self._add_audit_entry(
            version_id=version_id,
            action="submitted_for_approval",
            performed_by=requested_by,
            details={"request_id": request_id, "approvers": approvers}
        )
        return approval_request

    def approve_policy(self,
                       request_id: str,
                       approver: str,
                       approved: bool,
                       comments: str = "") -> ApprovalRequest:
        """
        Approve or reject a policy version
        """
        
        if request_id not in self.approval_requests:
            raise ValueError(f"Approval request {request_id} not found")
            
        request = self.approval_requests[request_id]
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request {request_id} is already in state {request.status.value}")
            
        if approver not in request.approvers:
            raise ValueError(f"{approver} is not authorized to approve this request")
            
        current_time = datetime.now(timezone.utc).isoformat()
        
        request.approvals.append({
            "approver": approver,
            "approved": approved,
            "timestamp": current_time,
            "comments": comments
        })
        
        if comments:
            request.comments.append({
                "user": approver,
                "timestamp": current_time,
                "comment": comments
            })
            
        if not approved:
            request.status = ApprovalStatus.REJECTED
            request.resolved_at = current_time
            
            version = self.versions[request.version_id]
            version.status = PolicyStatus.DRAFT
            
            self._add_audit_entry(
                version_id=request.version_id,
                action="rejected",
                performed_by=approver,
                details={"request_id": request_id, "reason": "Explicit rejection"}
            )
            
        elif len(request.approvals) >= len(request.approvers):
            if all(a["approved"] for a in request.approvals):
                request.status = ApprovalStatus.APPROVED
                request.resolved_at = current_time
                
                version = self.versions[request.version_id]
                version.status = PolicyStatus.APPROVED
                version.approved_by = approver
                version.approved_at = current_time
                
                self._add_audit_entry(
                    version_id=request.version_id,
                    action="approved",
                    performed_by=approver,
                    details={"request_id": request_id}
                )
        
        return request

    async def embed_approved_policy(self, version_id: str, performer: str) -> Dict[str, Any]:
        """
        Autonomous policy embedding: called by Orchestrator upon final approval.
        Wraps the synchronous activation logic in a separate thread."""
        if version_id not in self.versions:
            raise ValueError(f"Policy version {version_id} not found for embedding.")
            
        version = self.versions[version_id]
        
        if version.status != PolicyStatus.APPROVED:
            raise ValueError(f"Policy {version_id} is in status {version.status.value}. Must be APPROVED to embed.")
            
        try:
            activated_version = await asyncio.to_thread(self.activate_version, version_id, performer)
            
            self._add_audit_entry(
                version_id=version_id,
                action="auto_embedded",
                performed_by=performer,
                details={"message": "Policy was autonomously activated following final DAO decision."}
            )
            return {
                "status": "SUCCESS",
                "policy_id": version.policy_id,
                "version_number": activated_version.version_number,
                "message": "Policy successfully activated and embedded into compliance engine."
            }
        except Exception as e:
            raise RuntimeError(f"Autonomous Policy Embedding Failed: {e}")

    async def rollback_on_audit_failure(self, policy_id: str, rule_id_to_find: str, performed_by: str = "AUTO_ROLLBACK_AGENT") -> Dict[str, Any]:
        """
        [FIX 3: REMEDIATION GAP] Executes policy rollback based on a critical audit log failure.
        Finds the parent (previous) version of the currently active policy and activates it transactionally.
        """
        # Find the active version (synchronous method, must run in a thread if in an async context)
        active_version = await asyncio.to_thread(self.get_active_version, policy_id)
                
        if not active_version:
            raise ValueError(f"No active policy found for ID: {policy_id}")
                    
        parent_version_id = active_version.parent_version
                
        if not parent_version_id or parent_version_id not in self.versions:
            return {"status": "SKIPPED", "message": "No previous version available for automated rollback."}
                    
        target_version = self.versions[parent_version_id]
        
        # CRITICAL FIX: We perform the status changes within a transaction 
        try:
            # 1. Prepare target version for activation
            target_version.status = PolicyStatus.APPROVED
            
            # 2. Execute the activation (which implicitly deprecates the old version)
            # The rollback is an operation that *must* succeed in the face of failure.
            async with local_pg_client.transaction("AutoRollbackAgent", f"Rollback_{policy_id}") as conn:
                # We trust the synchronous activate_version call handles the local object changes.
                rolled_back_version = await asyncio.to_thread(self.activate_version, target_version.version_id, performed_by)

                # Simulate DB update to status table (critical for transactional proof)
                # NOTE: This assumes a table exists for policy status/version pointers
                await conn.execute(
                    "UPDATE policy_status_table SET active_version_id=$1, deprecated_version_id=$2 WHERE policy_id=$3",
                    rolled_back_version.version_id, active_version.version_id, policy_id
                )
                        
                self._add_audit_entry(
                    version_id=target_version.version_id,
                    action="auto_rolled_back",
                    performed_by=performed_by,
                    details={"reason": f"Critical failure detected by rule {rule_id_to_find}.\nActive policy {active_version.version_number} was deprecated."}
                )
                        
                return {
                    "status": "SUCCESS", 
                    "policy_id": policy_id,
                    "old_version": active_version.version_number,
                    "new_version": rolled_back_version.version_number
                }
        except Exception as e:
            logger.critical(f"TRANSACTIONAL Rollback Failed for {policy_id}: {e}")
            raise RuntimeError(f"Automated Rollback Failed: {e}")

    def activate_version(self, version_id: str, activated_by: str) -> PolicyVersion:
        """
        Activate an approved policy version
        Automatically deprecates previous active version
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
            
        version = self.versions[version_id]
        
        if version.status != PolicyStatus.APPROVED:
            raise ValueError(f"Only APPROVED versions can be activated (Current status: {version.status.value})")
            
        policy_id = version.policy_id
        current_time = datetime.now(timezone.utc).isoformat()
        
        if policy_id in self.active_versions:
            old_version_id = self.active_versions[policy_id]
            if old_version_id in self.versions and old_version_id != version_id:
                old_version = self.versions[old_version_id]
                old_version.status = PolicyStatus.DEPRECATED
                old_version.deprecated_at = current_time
                
                self._add_audit_entry(
                    version_id=old_version_id,
                    action="deprecated",
                    performed_by=activated_by,
                    details={"replaced_by": version_id}
                )
        
        version.status = PolicyStatus.ACTIVE
        version.activated_at = current_time
        self.active_versions[policy_id] = version_id
        
        self._add_audit_entry(
            version_id=version_id,
            action="activated",
            performed_by=activated_by,
            details={"policy_id": policy_id}
        )
        return version

    def rollback_to_version(self,
                            policy_id: str,
                            target_version_id: str,
                            performed_by: str) -> PolicyVersion:
        """
        Rollback to a previous policy version (manual operation)
        """
        if target_version_id not in self.versions:
            raise ValueError(f"Target version {target_version_id} not found")
            
        target_version = self.versions[target_version_id]
        if target_version.policy_id != policy_id:
            raise ValueError(f"Version {target_version_id} does not belong to policy {policy_id}")
            
        target_version.status = PolicyStatus.APPROVED
        
        return self.activate_version(target_version_id, performed_by)

    def get_active_version(self, policy_id: str) -> Optional[PolicyVersion]:
        """
        Get currently active version of a policy
        """
        if policy_id not in self.active_versions:
            return None
            
        version_id = self.active_versions[policy_id]
        return self.versions.get(version_id)

    def get_version_history(self, policy_id: str) -> List[PolicyVersion]:
        """
        Get all versions of a policy, ordered by creation date
        """
        if policy_id not in self.policy_index:
            return []
            
        version_ids = self.policy_index[policy_id]
        versions = [self.versions[vid] for vid in version_ids if vid in self.versions]
        versions.sort(key=lambda v: v.created_at, reverse=True)
        return versions

    def compare_versions(self, version_id_1: str, version_id_2: str) -> Dict[str, Any]:
        """
        Compare two policy versions
        """
        if version_id_1 not in self.versions or version_id_2 not in self.versions:
            raise ValueError("One or both versions not found")
            
        v1 = self.versions[version_id_1]
        v2 = self.versions[version_id_2]
        
        return {
            "version_1": {
                "version_id": v1.version_id,
                "version_number": v1.version_number,
                "status": v1.status.value, 
                "created_at": v1.created_at,
                "content_hash": v1.content_hash
            },
            "version_2": {
                "version_id": v2.version_id,
                "version_number": v2.version_number,
                "status": v2.status.value, 
                "created_at": v2.created_at,
                "content_hash": v2.content_hash
            },
            "content_changed": v1.content_hash != v2.content_hash,
            "status_changed": v1.status != v2.status
        }

    def get_version_by_id(self, version_id: str) -> Optional[PolicyVersion]:
        """Helper to get a specific version by ID."""
        return self.versions.get(version_id)

    def _add_audit_entry(self, version_id: str, action: str,
                          performed_by: str, details: Dict[str, Any]):
        """
        Add entry to audit trail
        """
        current_time_str = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        audit_id = f"AUDIT_{version_id}_{action}_{current_time_str}"
        
        entry = PolicyAuditEntry(
            audit_id=audit_id,
            version_id=version_id,
            action=action,
            performed_by=performed_by,
            details=details,
            # performed_at is handled by default_factory
        )
        self.audit_trail.append(entry)

    def get_audit_trail(self, version_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get audit trail for a specific version or all versions
        """
        if version_id:
            entries = [e for e in self.audit_trail if e.version_id == version_id]
        else:
            entries = self.audit_trail
            
        return [asdict(e) for e in entries]

    def export_version_as_json(self, version_id: str) -> str:
        """
        Export policy version as JSON
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
            
        version = self.versions[version_id]
        version_dict = asdict(version)
        version_dict["status"] = version.status.value
        version_dict["content"] = version.content
        return json.dumps(version_dict, indent=2)

# Global instance
policy_versioning_service = PolicyVersioningService()