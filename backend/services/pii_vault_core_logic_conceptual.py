from services.pqc_pii_layer import PQCEncryptionWrapper
from services.duckdb_store import udm_store
import json
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

MOCK_CIPHERTEXT_PREFIX = settings.PII_MOCK_CIPHERTEXT_PREFIX if hasattr(settings, 'PII_MOCK_CIPHERTEXT_PREFIX') else "MOCK_CIPHER_FOR_"
MOCK_PQC_KEY = settings.PII_MOCK_PQC_KEY.get_secret_value() if hasattr(settings.PII_MOCK_PQC_KEY, 'get_secret_value') else "MOCK_PQC_KEY_12345"
POLICY_PAYROLL_PURPOSE = settings.PII_POLICY_PAYROLL_PURPOSE if hasattr(settings, 'PII_POLICY_PAYROLL_PURPOSE') else "PAYROLL"
POLICY_ESS_PURPOSE = settings.PII_POLICY_ESS_PURPOSE if hasattr(settings, 'PII_POLICY_ESS_PURPOSE') else "ESS_PROFILE_ACCESS"
POLICY_ADMIN_ROLE_SUFFIX = settings.PII_POLICY_ADMIN_ROLE_SUFFIX if hasattr(settings, 'PII_POLICY_ADMIN_ROLE_SUFFIX') else 'ADMIN'
POLICY_EMPLOYEE_ID_PREFIX = settings.PII_POLICY_EMPLOYEE_ID_PREFIX if hasattr(settings, 'PII_POLICY_EMPLOYEE_ID_PREFIX') else 'EMP'
AUDIT_ACTION_DECRYPT = 'PII_DETOKENIZE'


def decrypt_pii(ciphertext: str, encryption_key: str) -> str:
    if encryption_key == MOCK_PQC_KEY:
        return ciphertext.replace(MOCK_CIPHERTEXT_PREFIX, "PLAINTEXT_")
    raise ValueError("Invalid PQC Key for decryption.")


class PIIVaultCore:
    def __init__(self):
        pass

    async def detokenize_and_decrypt(self, token: str, audit_context: Dict[str, Any]) -> str:
        metadata = self._get_pii_metadata(token)
        if not metadata:
            raise ValueError("PII token not found.")

        if not self._check_access_policy(audit_context):
            self._log_access_attempt(audit_context, metadata, success=False, reason="Policy Denied")
            raise PermissionError("Access to PII denied by Zero-Trust policy.")

        try:
            plaintext = decrypt_pii(metadata['ciphertext'], metadata['encryption_key'])
            self._log_access_attempt(audit_context, metadata, success=True)
            return plaintext
        except Exception as e:
            self._log_access_attempt(audit_context, metadata, success=False, reason=str(e))
            raise RuntimeError("Decryption failed.")

    def _get_pii_metadata(self, token: str) -> Dict[str, Any]:
        return {
            'ciphertext': f"{MOCK_CIPHERTEXT_PREFIX}{token}",
            'encryption_key': MOCK_PQC_KEY,
            'employee_uuid': token.split('_')[1] if '_' in token else 'UNKNOWN',
            'pii_type': 'SSN'
        }

    def _check_access_policy(self, context: Dict[str, Any]) -> bool:
        user_id = context.get('user_id', '').upper()
        purpose = context.get('purpose', '').upper()

        if purpose == POLICY_PAYROLL_PURPOSE and user_id.endswith(POLICY_ADMIN_ROLE_SUFFIX):
            return True

        if purpose == POLICY_ESS_PURPOSE and user_id.startswith(POLICY_EMPLOYEE_ID_PREFIX):
            return True

        return False

    def _log_access_attempt(self, context: Dict[str, Any], metadata: Dict[str, Any], success: bool, reason: Optional[str] = None):
        log_entry = {
            'audit_id': str(uuid.uuid4()),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'actor_id': context['user_id'],
            'action': AUDIT_ACTION_DECRYPT,
            'target_entity': metadata.get('employee_uuid', 'N/A'),
            'pii_type': metadata.get('pii_type', 'N/A'),
            'purpose': context.get('purpose', 'N/A'),
            'success': success,
            'reason': reason
        }
        logger.info(f"AUDIT PII: {log_entry}")
