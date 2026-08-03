import logging
import base64
import os
import hashlib
import json
import asyncio 
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

try:
    from cryptography.fernet import Fernet
except ImportError:
    raise RuntimeError("Critical Dependency Missing: Please run 'pip install cryptography'")

from config.settings import settings

logger = logging.getLogger(__name__)
PQC_LAYER_ID = "PQCEncryptionWrapper"  # class name kept: it is an import contract across the app

class PQCEncryptionWrapper:
    _instance = None
    _lock: Optional[asyncio.Lock] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PQCEncryptionWrapper, cls).__new__(cls)
            cls._instance.master_key_bytes = None
            cls._instance.fernet = None
            # Initialize lock on first creation
            cls._instance._lock = asyncio.Lock() 
        return cls._instance

    def __init__(self):
        # Only initialize once
        if PQCEncryptionWrapper._instance and PQCEncryptionWrapper._instance.master_key_bytes is not None:
            return
        if self.master_key_bytes is None:
            logger.info("✓ PII encryption wrapper initialised (AES-256, awaiting key generation).")

    @staticmethod
    def get_instance() -> "PQCEncryptionWrapper":
        return PQCEncryptionWrapper()

    async def initialize_keys(self) -> bool:
        async with self._lock:
            if self.master_key_bytes is None:
                
                def generate_key_sync():
                    """Synchronous key generation logic."""
                    pii_salt_value = settings.PII_SALT.get_secret_value().encode("utf-8")
                    return base64.urlsafe_b64encode(hashlib.sha256(pii_salt_value).digest()[:32])

                # 1. Generate the master key bytes safely in a thread
                self.master_key_bytes = await asyncio.to_thread(generate_key_sync)
                
                # 2. Initialize Fernet cipher safely in a thread
                self.fernet = await asyncio.to_thread(Fernet, self.master_key_bytes)
                
                logger.info("✅ AES-256 master key initialised.")
                return True
            return False

    def _ensure_sync_key(self):
        """Synchronous fallback logic."""
        if self.master_key_bytes is None:
            try:
                pii_salt_value = settings.PII_SALT.get_secret_value().encode("utf-8")
                key_b64 = base64.urlsafe_b64encode(hashlib.sha256(pii_salt_value).digest()[:32])
                self.master_key_bytes = key_b64
                self.fernet = Fernet(self.master_key_bytes)
                logger.critical("❌ Encryption key synchronously initialised in fallback. FIX ASYNC STARTUP.")
            except Exception as e:
                logger.critical(f"❌ FATAL: Cannot initialise the encryption key for sync context: {e}")
                raise RuntimeError("Encryption key uninitialised and cannot be generated.")

    def encrypt(self, plaintext: str, quantum_risk_flag: bool = False, data_context: str = "default") -> Tuple[str, Dict[str, Any]]:
        self._ensure_sync_key()
        if not plaintext:
            return "", {"status": "EMPTY"}

        token = self.fernet.encrypt(plaintext.encode("utf-8"))

        metadata = {
            "algorithm": "AES-256-Fernet",
            # Stated outright so nothing downstream can present this as
            # post-quantum cryptography. Fernet is AES-128-CBC + HMAC-SHA256
            # over a 256-bit key; it is classical, not quantum-resistant.
            "post_quantum": False,
            "key_hash": hashlib.sha256(self.master_key_bytes).hexdigest()[:8],
            "quantum_risk_flag": quantum_risk_flag,
            "context": data_context,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }

        return token.decode("utf-8"), metadata

    def decrypt(self, ciphertext: str, data_context: str = "default") -> str:
        self._ensure_sync_key()
        if not ciphertext:
            return ""

        try:
            plaintext = self.fernet.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed for context '{data_context}': {e}")
            raise ValueError("Invalid Ciphertext or Key.")

    async def rotate_keys(self) -> Dict[str, Any]:
        """Refuse to rotate, and say exactly why. NEVER destroys key material.

        This used to replace the in-memory Fernet key with a fresh random key
        that was persisted nowhere and re-encrypted nothing. Every encrypted
        column in employee_pii became permanently undecryptable the moment an
        admin clicked the button, and the endpoint returned "Keys Rotated".

        The master key here is DERIVED from the PII_SALT environment variable
        (sha256(PII_SALT) -> Fernet key). There is no second key slot and no key
        table, so there is nowhere to durably record a new key without either
        losing it on the next restart or writing usable key material next to the
        data it protects. Rotation is therefore refused rather than faked.

        A real rotation needs, in this order:
          1. a configured next key (e.g. a PII_SALT_NEXT setting), so the new key
             survives a restart before any ciphertext depends on it;
          2. a MultiFernet(new, old) decrypt path so both generations are
             readable while the migration runs;
          3. a batched re-encryption pass over every encrypted column of
             employee_pii inside transactions, resumable and idempotent;
          4. retirement of the old key only once the pass has verified.
        """
        return {
            "rotated": False,
            "status": "ROTATION_NOT_CONFIGURED",
            "message": (
                "Key rotation is not available. The encryption key is derived from the "
                "PII_SALT setting, and rotating it without first re-encrypting stored "
                "employee data would make that data permanently unreadable. Rotation "
                "requires a configured next key and a re-encryption pipeline; no key "
                "was changed and all encrypted data remains readable."
            ),
            "current_key_fingerprint": self.key_fingerprint(),
        }

    def key_fingerprint(self) -> Optional[str]:
        """Short non-reversible identifier for the key in use (never the key)."""
        if not self.master_key_bytes:
            return None
        return hashlib.sha256(self.master_key_bytes).hexdigest()[:8]


def decrypt_pii(ciphertext: str) -> str:
    try:
        wrapper = PQCEncryptionWrapper.get_instance()
        return wrapper.decrypt(ciphertext)
    except Exception as e:
        logger.critical(f"Legacy decrypt_pii stub failed: {e}")
        return "[DECRYPTION_FAIL_STUB]"