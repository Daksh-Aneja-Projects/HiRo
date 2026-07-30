# /backend/services/pii_vault.py - FIXED
import logging
from typing import Dict, Any, List, Optional, Union # CRITICAL FIX: Added Union
import asyncio
import uuid
from services.pqc_pii_layer import PQCEncryptionWrapper 
from services.postgres_client import pg_client 
from services.schemas.models import AuthPayload # CRITICAL FIX: Ensure AuthPayload is imported

logger = logging.getLogger(__name__)

class PIIVault:
    _instance = None
    
    def __init__(self):
        if PIIVault._instance: raise Exception("Singleton")
        self.pqc = PQCEncryptionWrapper.get_instance()
        # CRITICAL FIX: Define PII fields based on actual encrypted columns in `employee_pii` DDL
        self.pii_fields = {
            "employee_pii": [
                "full_name_encrypted", 
                "email_encrypted", 
                "phone_encrypted", 
                "national_id_encrypted"
            ]
        }
        logger.info("✓ PII Vault Initialized.")

    @staticmethod
    def get_instance():
        if not PIIVault._instance: PIIVault._instance = PIIVault()
        return PIIVault._instance

    # CRITICAL FIX: Clarify the `auth` argument is optional, as calling functions often only pass agent_id string.
    async def execute_pii_query(self, query: str, table_name: str, agent_id: str, auth: Optional[Union[AuthPayload, Dict[str, Any]]] = None, *args) -> List[Dict]:
        """
        Executes query -> Checks Access -> Decrypts PII.
        """
        # 1. Authorization Check (Simplified mock, relying on agent_id/role being passed)
        if agent_id in ["Unauthorized", "employee"] and table_name == "employee_pii": 
             # Mock policy: Employees can only view their own non-PII, not raw vault data
             # This simple check allows managers and admins (or HR agents) to proceed
             if auth is None:
                 raise PermissionError("PII Access Denied: Authentication context is missing.")
             # NOTE: A real vault uses fine-grained checks (e.g., scope, jurisdiction, consent)

        # 2. Execute
        # We assume the query selects encrypted fields based on the table_name
        raw_rows = await pg_client.fetch(query, *args)
        if not raw_rows: return []

        # 3. Decrypt
        decrypted_rows: List[Dict] = []
        # CRITICAL FIX: Get the list of encrypted fields for the *current* table
        fields = self.pii_fields.get(table_name, []) 
        
        for row in raw_rows:
            new_row = row.copy()
            # CRITICAL FIX: Iterate over the list of known encrypted fields
            for field in fields:
                # Check if the field was actually returned by the SQL query and contains a value
                encrypted_value = row.get(field)
                if encrypted_value and isinstance(encrypted_value, str):  # attempt decrypt on any stored ciphertext (real Fernet tokens)
                    try:
                        # PQC Decrypt (Synchronous operation, assumed fast enough or managed by `to_thread` in caller if needed)
                        val = self.pqc.decrypt(encrypted_value)
                        new_row[field.replace('_encrypted', '')] = val # Store decrypted value under the clear name
                        del new_row[field] # Remove the encrypted field
                    except Exception:
                        new_row[field.replace('_encrypted', '')] = "[DECRYPTION_FAILED]"
                        del new_row[field]

            decrypted_rows.append(new_row)
        
        logger.info(f"Decrypted {len(decrypted_rows)} records for {agent_id}")
        return decrypted_rows