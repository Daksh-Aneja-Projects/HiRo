import logging
import base64
import os
import hashlib
import json
import asyncio 
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone # CRITICAL FIX: Add timezone import for metadata

try:
    from cryptography.fernet import Fernet
except ImportError:
    raise RuntimeError("Critical Dependency Missing: Please run 'pip install cryptography'")

from config.settings import settings

logger = logging.getLogger(__name__)
PQC_LAYER_ID = "PQCEncryptionWrapper"

class PQCEncryptionWrapper:
    _instance = None
    _lock: Optional[asyncio.Lock] = None # CRITICAL FIX: Added Lock

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
            logger.info("✓ PII Encryption Wrapper (PQC) Initialized (Awaiting Key Generation).")

    @staticmethod
    def get_instance() -> "PQCEncryptionWrapper":
        return PQCEncryptionWrapper()

    async def initialize_keys(self) -> bool:
        # CRITICAL FIX: Use the lock to ensure only one coroutine generates the key
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
                
                logger.info("✅ PQC/AES Master Key initialized.")
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
                logger.critical("❌ PQC keys synchronously initialized in fallback. FIX ASYNC STARTUP.")
            except Exception as e:
                logger.critical(f"❌ FATAL: Cannot initialize PQC keys for sync context: {e}")
                raise RuntimeError("PQC Keys uninitialized and cannot be generated.")

    def encrypt(self, plaintext: str, quantum_risk_flag: bool = False, data_context: str = "default") -> Tuple[str, Dict[str, Any]]:
        self._ensure_sync_key()
        if not plaintext:
            return "", {"status": "EMPTY"}

        token = self.fernet.encrypt(plaintext.encode("utf-8"))

        metadata = {
            "algorithm": "AES-256-Fernet",
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

    async def rotate_keys(self) -> bool:
        async with self._lock:
            # CRITICAL FIX: Key generation should be a thread-safe call
            self.master_key_bytes = await asyncio.to_thread(Fernet.generate_key)
            self.fernet = await asyncio.to_thread(Fernet, self.master_key_bytes)
            logger.warning("🔑 PQC Master Key Rotated.\nData re-encryption is now required!")
            return True


def decrypt_pii(ciphertext: str) -> str:
    try:
        wrapper = PQCEncryptionWrapper.get_instance()
        return wrapper.decrypt(ciphertext)
    except Exception as e:
        logger.critical(f"Legacy decrypt_pii stub failed: {e}")
        return "[DECRYPTION_FAIL_STUB]"