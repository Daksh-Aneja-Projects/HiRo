# backend/services/pii_vault.py
import logging
from typing import Dict, Any, List, Optional, Union
import asyncio
import uuid
from services.pqc_pii_layer import PQCEncryptionWrapper 
from services.postgres_client import pg_client 
from services.schemas.models import AuthPayload

logger = logging.getLogger(__name__)

class PIIVault:
    _instance = None
    
    def __init__(self):
        if PIIVault._instance: raise Exception("Singleton")
        self.pqc = PQCEncryptionWrapper.get_instance()
        self.pii_fields = {
            "employee_pii": [
                "full_name_encrypted",
                "email_encrypted",
                "phone_encrypted",
                "national_id_encrypted",
                "base_salary_encrypted",
                "bonus_target_encrypted",
            ]
        }
        logger.info("✓ PII Vault Initialized.")

    @staticmethod
    def get_instance():
        if not PIIVault._instance: PIIVault._instance = PIIVault()
        return PIIVault._instance

    def encrypt(self, plaintext: str, data_context: str = "default"):
        """Encrypt a value for storage in one of the *_encrypted columns.

        The vault only ever exposed a read path, so update_compensation called
        self.vault.encrypt(...) and raised AttributeError before it touched the
        database. Every pay change in the product failed at the first line, and
        comp_history never held a row.

        Returns (ciphertext, metadata) to match the crypto layer it delegates to.
        """
        return self.pqc.encrypt(plaintext, data_context=data_context)

    def decrypt(self, ciphertext: str, data_context: str = "default") -> str:
        """Read a single value back out of an encrypted column."""
        return self.pqc.decrypt(ciphertext, data_context=data_context)

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
        fields = self.pii_fields.get(table_name, []) 
        
        for row in raw_rows:
            new_row = row.copy()
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