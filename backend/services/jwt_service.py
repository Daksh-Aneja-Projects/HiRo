# backend/services/jwt_service.py
"""JWT Service: Centralized, robust service for creating, encoding, and decoding JSON Web Tokens.
Used by the AuthService to manage user sessions and tokens."""
import logging
import jwt
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from config.settings import settings

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
try:
    SECRET_KEY = settings.JWT_SECRET_KEY.get_secret_value()
except AttributeError:
    SECRET_KEY = getattr(settings, 'JWT_SECRET_KEY', "super_secret_signing_key_for_hiro")
    if SECRET_KEY == "super_secret_signing_key_for_hiro":
         logger.critical("Using insecure default JWT secret key.")

ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

class JWTService:
    """
    Manages the cryptographic operations for issuing and validating JWTs.
    """
    def __init__(self):
        if not SECRET_KEY or not ALGORITHM:
            logger.critical("JWT_SECRET_KEY or JWT_ALGORITHM is not set in settings.")
            raise RuntimeError("JWT configuration missing.")
        logger.info(f"✓ JWT Service Initialized (Algorithm: {ALGORITHM}).")

    def create_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Creates a signed JWT with 
        standard claims (iss, exp, sub, iat)."""
        to_encode = data.copy()
        
        now_utc = datetime.now(timezone.utc)
        
        # Determine Expiration
        if expires_delta:
            expire = now_utc + expires_delta
        else:
            expire = now_utc + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            
        # Add Standard Claims
        to_encode.update({
            "exp": expire,
            "iat": now_utc,
            "iss": "HiRo-AuthService"
        })
        
        # Ensure 'sub' (subject) is present
        if 'sub' not in to_encode and 'username' in data:
            to_encode['sub'] = data['username']
            
        try:
            token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM) 
            return token
        except Exception as e:
            logger.error(f"Failed to encode JWT: {e}")
            raise ValueError("Token generation failed.")

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decodes and validates a JWT, raising specific exceptions on failure."""
        try:
            # Decode and Validate
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                options={
                    "require": ["exp", "sub", "iat", "iss"], 
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iss": True,
                    "leeway": timedelta(seconds=10) # Add slight leeway for clock drift
                },
                issuer="HiRo-AuthService"
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token decode failed: Signature expired.")
            raise ValueError("Token has expired.")
        except jwt.InvalidSignatureError:
            logger.warning("Token decode failed: Invalid signature.")
            raise ValueError("Token signature is invalid.")
        except jwt.InvalidIssuerError:
            logger.warning("Token decode failed: Invalid issuer.")
            raise ValueError("Token has an invalid issuer.")
        except jwt.InvalidAlgorithmError:
            logger.error("Token decode failed: Invalid algorithm.")
            raise ValueError("Token uses an invalid algorithm.")
        except jwt.PyJWTError as e:
            logger.error(f"Token decode failed (General): {e}")
            raise ValueError("Could not validate credentials.")

# Global Instance
jwt_service = JWTService()
