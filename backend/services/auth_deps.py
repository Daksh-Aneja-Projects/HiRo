# backend/services/auth_deps.py
"""Authorization Dependencies: Provides reusable functions for FastAPI route security, including JWT verification, RBAC enforcement, and data sanitization."""
import logging
from typing import Dict, Any, Optional, List, Union
from fastapi import Header, HTTPException, status, Depends
from pydantic import BaseModel
from config.settings import settings
from services.jwt_service import JWTService 
from datetime import datetime, timezone 

logger = logging.getLogger(__name__)

# --- AuthPayload Model (Must match JWT payload structure) ---
class AuthPayload(BaseModel):
    sub: str  # username
    role: str  # user role (e.g., 'hrit_admin')
    user_id: str
    email: str
    employee_uuid: Optional[str] = None  # maps the user to their Postgres employee record
    exp: Optional[int] = None

# Global instance of the service wrapper
jwt_service = JWTService()

# --- NOTE: Removed 'AGENT_SIGNING_SECRET' definition as it belongs in settings.py ---

def get_auth_payload(token: Optional[str] = Header(None, alias="Authorization")) -> AuthPayload:
    """Dependency to verify JWT token and extract payload."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing Authorization header"
        )
    scheme, _, token_value = token.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Must be 'Bearer'."
        )
    try:
        payload = jwt_service.decode_token(token_value)
        return AuthPayload(**payload) 
    except Exception as e:
        logger.error(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )

# --- RBAC Helper ---
def _role_checker(allowed_roles: List[str], payload: AuthPayload) -> Dict[str, Any]:
    """
    Reusable function to check if the user's role is in the allowed list.
    Returns the payload dictionary on success, allowing downstream functions to access user data like dict.
    """
    if payload.role not in allowed_roles:
        logger.warning(f"Access denied for user {payload.sub} with role {payload.role}. Required: {allowed_roles}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
        )
    return payload.model_dump()

# --- RBAC Dependency Functions (Aligned with Frontend Portals) ---

def hrit_admin_role_required(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
    """Requires HRIT Admin role (Full system access)."""
    return _role_checker(["hrit_admin"], payload)

def policy_admin_role_required(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
    """Requires Policy Admin role (HRIT Admin or HRBP)."""
    return _role_checker(["hrit_admin", "hrbp"], payload)

def hrbp_role_required(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
    """Requires HR Business Partner role or higher."""
    return _role_checker(["hrit_admin", "hrbp"], payload)

def manager_role_required(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
    """Requires Manager role or higher (MSS)."""
    return _role_checker(["hrit_admin", "hrbp", "manager"], payload)

def employee_role_required(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
    """Requires Employee role or any authenticated role (ESS)."""
    return _role_checker(["hrit_admin", "hrbp", "manager", "employee"], payload)

def admin_or_data_migrator_required(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
    """Requires a privileged role capable of triggering large-scale data ops."""
    return _role_checker(["hrit_admin", "data_migrator"], payload)

# --- Get Current User Payload ---
async def get_current_user_payload(payload: AuthPayload = Depends(get_auth_payload)) -> Dict[str, Any]:
       """Returns the cleaned user payload, used for all authenticated routes."""
       return payload.model_dump()

# --- Portal Access Check Functions ---
def check_portal_access(user: Dict[str, Any], portal: str) -> bool:
    """Check if user has access to a specific portal. Used for internal service checks."""
    user_role = user.get("role", "").lower()
    
    # Define portal access by role (Matches Frontend PortalAccess.js)
    portal_access_map = {
        "admin-portal": ["hrit_admin"], 
        "hr-portal": ["hrit_admin", "hrbp"], 
        "hrit-portal": ["hrit_admin"], 
        "manager-portal": ["hrit_admin", "manager", "hrbp"],
        "employee-portal": ["hrit_admin", "hrbp", "manager", "employee"]
    }
        
    allowed_roles = portal_access_map.get(portal, [])
    return user_role in allowed_roles