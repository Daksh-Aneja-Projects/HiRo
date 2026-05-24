# /backend/services/auth_service.py — HiRo Authentication Service
"""Authentication Service: Production-grade auth with bcrypt hashing and proper RBAC."""
import logging
import os
from typing import Dict, Any, Optional
from datetime import timedelta

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    import hashlib
    HAS_BCRYPT = False

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings
from services.jwt_service import JWTService
from bson import ObjectId

logger = logging.getLogger(__name__)

USER_COLLECTION = "users"


class PasswordHasher:
    """Production-grade password hasher using bcrypt with fallback to PBKDF2."""

    @staticmethod
    def hash_password(password: str) -> str:
        if HAS_BCRYPT:
            salt = bcrypt.gensalt(rounds=12)
            return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        else:
            # Fallback: PBKDF2 with SHA-256 (still secure, just slower startup)
            salt = os.urandom(32)
            import hashlib
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
            return f"pbkdf2:{salt.hex()}:{dk.hex()}"

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        try:
            if HAS_BCRYPT and hashed_password.startswith("$2"):
                return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
            elif hashed_password.startswith("pbkdf2:"):
                _, salt_hex, dk_hex = hashed_password.split(":")
                salt = bytes.fromhex(salt_hex)
                import hashlib
                dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
                return dk.hex() == dk_hex
            elif hashed_password.startswith("HASHED_"):
                # Legacy compatibility: migrate on next login
                import hashlib
                expected = f"HASHED_{hashlib.sha256(password.encode('utf-8')).hexdigest()}"
                return expected == hashed_password
            else:
                return False
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False


class AuthService:
    def __init__(self, mongo_client: AsyncIOMotorClient):
        self.db = mongo_client[settings.MONGO_DB_NAME]
        self.users_collection = self.db[USER_COLLECTION]
        self.jwt_service = JWTService()
        self.hasher = PasswordHasher()
        logger.info(" ✓  HiRo Auth Service initialized (bcrypt=%s)", HAS_BCRYPT)

    async def initialize_test_users(self):
        """Seeds the database with test users for development. Only runs in dev mode."""
        if settings.ENV not in ("development", "dev", "test"):
            logger.info("Skipping test user seeding in %s environment", settings.ENV)
            return

        test_users = [
            {
                "username": "admin",
                "email": "admin@hiro.ai",
                "full_name": "System Admin",
                "role": "hrit_admin",
                "is_active": True,
            },
            {
                "username": "hritmanager",
                "email": "hritmanager@hiro.ai",
                "full_name": "Alice HRIT",
                "role": "hrit_admin",
                "is_active": True,
            },
            {
                "username": "hrbp",
                "email": "hrbp@hiro.ai",
                "full_name": "Bob HRBP Lead",
                "role": "hrbp",
                "is_active": True,
            },
            {
                "username": "manager",
                "email": "manager@hiro.ai",
                "full_name": "Charlie Manager",
                "role": "manager",
                "is_active": True,
            },
            {
                "username": "employee",
                "email": "employee@hiro.ai",
                "full_name": "Dana Employee",
                "role": "employee",
                "is_active": True,
            },
        ]

        logger.info("Seeding %d test users for development...", len(test_users))

        for user_spec in test_users:
            existing = await self.users_collection.find_one({"username": user_spec["username"]})
            if existing:
                # Only update non-password fields
                await self.users_collection.update_one(
                    {"username": user_spec["username"]},
                    {"$set": {
                        "email": user_spec["email"],
                        "full_name": user_spec["full_name"],
                        "role": user_spec["role"],
                        "is_active": user_spec["is_active"],
                    }},
                )
                logger.debug(" ✓  Updated test user: %s", user_spec["username"])
            else:
                user_spec["hashed_password"] = self.hasher.hash_password(user_spec["username"])
                user_spec["user_id"] = str(ObjectId())
                await self.users_collection.insert_one(user_spec)
                logger.debug(" ✓  Created test user: %s", user_spec["username"])

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return await self.users_collection.find_one({"username": username})

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = await self.get_user_by_username(username)
        if not user:
            logger.warning("Authentication failed: user not found (%s)", username)
            return None

        if not user.get("is_active", True):
            logger.warning("Authentication failed: account inactive (%s)", username)
            return None

        stored_hash = user.get("hashed_password", "")

        if not self.hasher.verify_password(password, stored_hash):
            logger.warning("Authentication failed: bad password (%s)", username)
            return None

        # Migrate legacy password hashes on successful login
        if stored_hash.startswith("HASHED_"):
            new_hash = self.hasher.hash_password(password)
            await self.users_collection.update_one(
                {"username": username},
                {"$set": {"hashed_password": new_hash}},
            )
            logger.info("Migrated legacy password hash for user: %s", username)

        logger.info("Authentication successful for user: %s", username)
        return {
            "username": user["username"],
            "role": user["role"],
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "is_active": user.get("is_active", True),
            "user_id": user.get("user_id", str(user.get("_id"))),
            "_id": user.get("_id"),
        }

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        return self.jwt_service.create_token(data, expires_delta)

    def decode_token(self, token: str) -> Dict[str, Any]:
        return self.jwt_service.decode_token(token)