# services/vv_compiler.py
"""
Verification & Validation Compiler: Provides syntactic and semantic checks 
for Business Process Compliance Logic (BPCL) by introspecting real UDM models.
"""
import logging
import re
from typing import Dict, Any, List, Type
import json
import asyncio
from services.udm_schemas_complete import (
    EmployeePIIDataProduct, LeaveRequestDataProduct, 
    CompensationDataProduct, PerformanceReviewDataProduct
)

logger = logging.getLogger(__name__)

UDM_MODEL_MAP: Dict[str, Type[Any]] = {
    "employee_profile": EmployeePIIDataProduct,
    "leave_request": LeaveRequestDataProduct,
    "compensation": CompensationDataProduct,
    "performance": PerformanceReviewDataProduct,
    "input": type('Input', (object,), {}), # Mock model for dynamic input context
    "context": type('Context', (object,), {}), # Mock model for global context
}

class VVCompiler:
    """
    Compiles and validates BPCL policy content using live Pydantic schema introspection.
    """
    def __init__(self):
        self.udm_schema = self._generate_schema_from_models()
        self.udm_schema["input"] = {"description": "Dynamic user input fields.", "columns": {}}
        self.udm_schema["context"] = {"description": "Global execution context.", "columns": {}}
        
        logger.info(f"✓ VVCompiler Initialized with {len(self.udm_schema)} UDM entities (including input/context).")

    def _generate_schema_from_models(self) -> Dict[str, Any]:
        """
        [SYNCHRONOUS] Dynamically builds the validation schema by inspecting Pydantic models.
        """
        schema = {}
        for table_name, model_class in UDM_MODEL_MAP.items():
            if not hasattr(model_class, 'model_json_schema'):
                # Skip mock models or non-Pydantic types
                continue
                
            properties = model_class.model_json_schema().get('properties', {})
            columns = {}
            for field_name, field_def in properties.items():
                f_type = field_def.get('type', 'string').upper()
                
                if 'enum' in field_def:
                    f_type = "ENUM"
                elif f_type in ('NUMBER', 'INTEGER'):
                    f_type = "NUMERIC"
                elif f_type == 'BOOLEAN':
                    f_type = "BOOLEAN"
                else:
                    f_type = "STRING"
                    
                columns[field_name] = {"type": f_type}
            
            schema[table_name] = {
                "description": model_class.__doc__,
                "columns": columns
            }
        return schema

    def _validate_syntactic_integrity(self, content: Dict[str, Any]) -> List[str]:
        """[SYNCHRONOUS] Checks for JSON structure and required keys."""
        errors = []
        if 'policy_name' not in content:
            errors.append("Missing required field: 'policy_name'")
        if 'rules' not in content or not isinstance(content.get('rules'), list):
            errors.append("Field 'rules' must be a list.")
            return errors

        for i, rule in enumerate(content['rules']):
            if not all(k in rule for k in ['id', 'condition', 'action']):
                errors.append(f"Rule {i+1} missing mandatory keys (id, condition, action).")
        return errors

    def _validate_semantic_integrity(self, policy_content: Dict[str, Any]) -> List[str]:
        """
        [SYNCHRONOUS] Validates that rules reference existing tables/columns in the UDM.
        """
        errors = []
        
        for rule in policy_content.get('rules', []):
            condition_str = rule.get('condition', '')
            
            # Finds tokens matching 'word.word' (ignoring case, but focusing on structure)
            references = re.findall(r'(\b\w+\.\w+\b)', condition_str)
            
            for token in references:
                try:
                    table_ref, column_ref = token.split('.', 1)
                    table_ref = table_ref.lower().strip() # Normalize table name
                    column_ref = column_ref.strip()
                    
                    if table_ref in self.udm_schema:
                        if table_ref not in ["input", "context"] and column_ref not in self.udm_schema[table_ref]['columns']:
                            errors.append(f"Rule '{rule.get('id')}' Invalid Column: {table_ref}.{column_ref}")
                    else:
                        errors.append(f"Rule '{rule.get('id')}' Invalid Table: {table_ref}")
                except ValueError:
                    # Should not happen with the regex above, but included for extreme safety
                    continue 
        return errors

    def validate_bpcl_sync(self, policy_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """[SYNCHRONOUS] Runs validation pipeline (internal sync method)."""
        syn_errors = self._validate_syntactic_integrity(content)
        if syn_errors:
            return {"is_valid": False, "errors": syn_errors, "type": "SYNTAX", "policy_id": policy_id}
            
        sem_errors = self._validate_semantic_integrity(content)
        if sem_errors:
            return {"is_valid": False, "errors": sem_errors, "type": "SEMANTIC", "policy_id": policy_id}
            
        return {"is_valid": True, "errors": [], "type": "ALL_PASSED", "policy_id": policy_id, "details": "Policy is compliant with UDM Schema."}

    async def validate_bpcl(self, policy_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        [ASYNCHRONOUS] Public interface to validate BPCL policy content safely.
        """
        return await asyncio.to_thread(self.validate_bpcl_sync, policy_id, content)