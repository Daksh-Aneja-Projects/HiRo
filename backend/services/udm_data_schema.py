# /C:/HiRo Project/backend/services/udm_data_schema.py
# /HiRo_backend/services/udm_data_schema.py
# backend/services/udm_data_schema.py
"""DEPRECATED: Please use udm_schemas_complete.py for the full data model definitions.
This file maintains backward compatibility by explicitly re-exporting core models."""
# CRITICAL FIX: Explicitly re-export core UDM classes used by legacy/seeding scripts 
# from the definitive source (udm_schemas_complete). Removed non-UDM imports (CompensationPlan, ConfigurationUpdate).
from .udm_schemas_complete import (
    EmployeePIIDataProduct, 
    LeaveBalanceDataProduct, 
    EmployeeRole, 
    JurisdictionCode,
    EmployeeStatus,
    RequisitionStatus,
    TimeClockDataProduct,
    CompensationDataProduct,
    PayrollRunDataProduct,
    PerformanceReviewDataProduct,
    SkillAssessmentDataProduct,
    BenefitsEnrollmentDataProduct,
    HRSDTicketDataProduct,
    AttritionRiskDataProduct, 
    SkillGapAnalysisDataProduct,
    OffboardingDataProduct,
    LeaveRequestDataProduct, 
)
# NOTE: The seeder script (`init_test_data.py`) has been updated to correctly import
# EmployeePIIDataProduct, LeaveBalanceDataProduct, and EmployeeRole from here, 
# ensuring backward compatibility while pointing to the unified source.
