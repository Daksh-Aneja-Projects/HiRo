# backend/services/comprehensive_routes.py
"""Aggregator for the comprehensive API surface.

The endpoints were split by domain into routes/<domain>_routes.py. Importing
those modules registers their handlers onto the shared router objects defined in
routes.comprehensive_common. Everything (routers, request models, shared helpers,
and the handler functions) is re-exported here so existing imports such as
`from services.comprehensive_routes import ALL_ROUTERS` and direct references to
handler/helper functions keep working unchanged.
"""
# Shared core: imports, request models, the 28 routers, ALL_ROUTERS, and helpers.
from routes.comprehensive_common import *  # noqa: F401,F403
from routes.comprehensive_common import (  # noqa: F401  (underscore names skip *)
    ALL_ROUTERS,
    _pvs, _policy_call, _readable_agent, _require_admin_service, _admin_audit,
    _audit_detail, _dev_persist, _parse_bpcl, _hr, _self_uuid, _reports_to,
    _scoped_employee_id, _owner_scope, _pending_leave_requests, _approval_queue,
    _generate_jd, _strip_code_fence, _twin_messages, _pqc, _consents,
    _workforce_analytics, _social_activities, _ideas, _BPCL_FIELD, _BPCL_CONSTRAINT,
)

# Domain handler modules. Importing each registers its routes on the shared
# routers (decorators run at import) and re-exports its handler functions here.
from routes.governance_routes import *  # noqa: F401,F403
from routes.hrsd_routes import *  # noqa: F401,F403
from routes.admin_ops_routes import *  # noqa: F401,F403
from routes.ai_data_routes import *  # noqa: F401,F403
from routes.hr_core_routes import *  # noqa: F401,F403
from routes.workforce_routes import *  # noqa: F401,F403
from routes.talent_ext_routes import *  # noqa: F401,F403
from routes.engagement_routes import *  # noqa: F401,F403
