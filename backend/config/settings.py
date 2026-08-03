# backend/config/settings.py

"""Configuration Settings for HiRo Enterprise Platform.
Loads environment variables and provides structured access to all
constants, ensuring compatibility with the multi-agent, streaming, and RBAC architecture."""

import os
import json as _json
import logging
from typing import Optional, List, Dict, Any
from pydantic import SecretStr

# --- Pydantic v1/v2 compatibility shim ---------------------------------------
# The stack pins pydantic 1.10.x (nats-py compat), but much of the code calls the
# v2-only BaseModel.model_dump()/model_validate(). Add them once here (settings is
# imported before anything constructs a model) so those calls don't 500 at runtime.
import pydantic as _pydantic
if _pydantic.VERSION.startswith("1."):
    # `model_config = ConfigDict(...)` is a v2 idiom; on v1 it becomes a stray field
    # that leaks into every response. Strip that inert artifact from serialization.
    _orig_dict = _pydantic.BaseModel.dict
    def _dict(self, **kw):
        d = _orig_dict(self, **kw)
        d.pop("model_config", None)
        return d
    _pydantic.BaseModel.dict = _dict
if not hasattr(_pydantic.BaseModel, "model_dump"):
    def _model_dump(self, *, mode=None, **kw):
        if mode == "json":
            d = _json.loads(self.json(**kw))
            d.pop("model_config", None)  # .json() bypasses the patched .dict()
            return d
        return self.dict(**kw)
    _pydantic.BaseModel.model_dump = _model_dump
if not hasattr(_pydantic.BaseModel, "model_validate"):
    _pydantic.BaseModel.model_validate = classmethod(lambda cls, obj: cls.parse_obj(obj))

logger = logging.getLogger(__name__)

# --- Environment Loading (Standard Practice) ---
# Local runs keep their config in backend/.env.local. Load it here so starting
# uvicorn directly behaves the same as starting it through run_local.ps1; a
# forgotten export otherwise silently falls back to the Docker hostnames and the
# server dials a `postgres_db` that does not exist outside compose.
# Real environment variables always win, so this is inert in any deployment.
def _load_env_file() -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            # Overrides deliberately: server.py loads the committed `.env` (which
            # carries the Docker hostnames) before this module is imported, so a
            # setdefault here would always lose to it and the local run would dial
            # `postgres_db`. `.env.local` is gitignored and absent in any real
            # deployment, which makes this inert outside a developer machine.
            os.environ[key.strip()] = value.strip()

_load_env_file()


def get_env_variable(key: str, default: Optional[str] = None) -> str:
    """Helper function to retrieve environment variables."""
    value = os.environ.get(key)
    if value is None and default is None:
        logger.warning(f"Configuration Warning: Environment variable '{key}' is not set and has no default.")
    return value if value is not None else (default if default is not None else "")

# --- Core Application Settings ---
class Settings:
    # --- Application Configuration ---
    APP_NAME: str = "HiRo Enterprise API"
    LOG_LEVEL: str = get_env_variable("LOG_LEVEL", "INFO")
    # Deployment environment; gates dev-only test-user seeding and prod secret checks.
    ENV: str = get_env_variable("ENV", "development")
    
    # CORS Configuration
    FRONTEND_URL: str = get_env_variable("FRONTEND_URL", "http://localhost:3000,http://127.0.0.1:3000")
    
    # Security / Upload Limits
    MAX_BODY_SIZE_MB: str = get_env_variable("MAX_BODY_SIZE_MB", "100")
    RATE_LIMIT_RPM: int = int(get_env_variable("RATE_LIMIT_RPM", "1000"))
    
    # --- Database Settings (Postgres UDM) ---
    POSTGRES_USER: str = get_env_variable("POSTGRES_USER", "hiro_user")
    # Using the production-grade password convention from the previous successful fix
    POSTGRES_PASSWORD: SecretStr = SecretStr(get_env_variable("POSTGRES_PASSWORD", "hiro_password_production"))
    POSTGRES_HOST: str = get_env_variable("POSTGRES_HOST", "postgres_db")
    POSTGRES_PORT: str = get_env_variable("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = get_env_variable("POSTGRES_DB", "hiro_db")
    
    def postgres_url(self) -> str:
        try:
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        except Exception:
            logger.critical("Failed to build Postgres URL: POSTGRES_PASSWORD retrieval failed.")
            return f"postgresql://{self.POSTGRES_USER}:MOCK_PASS@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def POSTGRES_URL(self) -> str:
        return self.postgres_url()
    
    # --- Database Settings (DGraph - for Graph/Ingestion) ---
    DGRAPH_URL: str = get_env_variable("DGRAPH_URL", "http://dgraph-alpha:8080")
    
    # --- Database Settings (MongoDB - for Legacy/Auth) ---
    MONGO_USER: str = get_env_variable("MONGO_USER", "admin")
    MONGO_PASSWORD: SecretStr = SecretStr(get_env_variable("MONGO_PASSWORD", get_env_variable("MONGO_ROOT_PASSWORD", "mongo_secret_production")))
    MONGO_HOST: str = get_env_variable("MONGO_HOST", "mongo")
    MONGO_PORT: str = get_env_variable("MONGO_PORT", "27017")
    MONGO_DB_NAME: str = get_env_variable("MONGO_DB_NAME", "ahcm_db")
    
    def mongo_url(self) -> str:
        # A full override wins (e.g. an auth-free local mongod: mongodb://localhost:27017).
        override = get_env_variable("MONGO_URI", "")
        if override:
            return override
        try:
            password_value = self.MONGO_PASSWORD.get_secret_value()
        except Exception:
            password_value = "MOCK_PASS"
        return f"mongodb://{self.MONGO_USER}:{password_value}@{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}?authSource=admin"
        
    # --- Redis Settings (Rate Limiting/Cache) ---
    REDIS_HOST: str = get_env_variable("REDIS_HOST", "redis")
    REDIS_PORT: str = get_env_variable("REDIS_PORT", "6379")
    REDIS_DB: str = get_env_variable("REDIS_DB", "0")
    
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # --- Authentication & JWT Settings ---
    ADMIN_USERNAME: str = get_env_variable("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: SecretStr = SecretStr(get_env_variable("ADMIN_PASSWORD", "secure_admin_password"))
    PII_SALT: SecretStr = SecretStr(get_env_variable("PII_SALT", "default_pii_salt_4096_secure"))
    
    PII_MOCK_PQC_KEY: SecretStr = SecretStr(get_env_variable("PII_MOCK_PQC_KEY", "MOCK_PQC_KEY_DEFAULT_FALLBACK"))
    
    DEFAULT_TEST_PASSWORD: SecretStr = SecretStr(get_env_variable("DEFAULT_TEST_PASSWORD", "testpass123"))
    # Using the longer, more secure key from previous final version
    JWT_SECRET_KEY: SecretStr = SecretStr(get_env_variable("JWT_SECRET_KEY", "hiro_production_signing_key_secure_48char"))
    JWT_ALGORITHM: str = get_env_variable("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(get_env_variable("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # --- Agent Communication (NATS JetStream) ---
    NATS_URL: str = get_env_variable("NATS_URL", "nats://nats:4222")
    NATS_JETSTREAM_DOMAIN: str = get_env_variable("NATS_JETSTREAM_DOMAIN", "HIRO_STREAM")
    NATS_MAX_RETRIES: int = int(get_env_variable("NATS_MAX_RETRIES", "5"))
    NATS_RETRY_SLEEP_SECONDS: float = float(get_env_variable("NATS_RETRY_SLEEP_SECONDS", "2.0"))
    NATS_CONNECT_TIMEOUT_SECONDS: float = float(get_env_variable("NATS_CONNECT_TIMEOUT_SECONDS", "5.0"))
    AGENT_SIGNING_SECRET: SecretStr = SecretStr(get_env_variable("AGENT_SIGNING_SECRET", "hiro_zero_trust_production_key_1001001"))
    HRIT_MANAGER_APPROVERS: List[str] = get_env_variable("HRIT_MANAGER_APPROVERS", "Alice_HRIT,Bob_Comp_VP").split(',')
    
    # --- Local AI Service (Ollama only) ---
    OLLAMA_BASE_URL: str = get_env_variable("OLLAMA_BASE_URL", "http://ollama:11434")
    # Default local model: llama3.1 8B — already pulled on this host, tool-calling capable, CPU-friendly.
    LLM_MODEL_NAME: str = get_env_variable("LLM_MODEL_NAME", "llama3.1:8b")
    # Local embedding model (nomic-embed-text -> 768-dim vectors, matches the pgvector column).
    EMBEDDING_MODEL: str = get_env_variable("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_DIM: int = int(get_env_variable("EMBEDDING_DIM", "768"))
    
    # --- Agent Configuration Defaults ---
    POLICY_SCRAPING_INTERVAL_SECONDS: int = int(get_env_variable("POLICY_SCRAPING_INTERVAL_SECONDS", str(3600 * 24)))
    DTLA_SCENARIO_INTERVAL_SECONDS: int = int(get_env_variable("DTLA_SCENARIO_INTERVAL_SECONDS", str(3600 * 24)))
    DTLA_RISK_THRESHOLD: float = float(get_env_variable("DTLA_RISK_THRESHOLD", "0.9"))
    EXTERNAL_API_TIMEOUT_SECONDS: float = float(get_env_variable("EXTERNAL_API_TIMEOUT_SECONDS", "45.0"))
    # Local LLM inference runs on CPU here, so a long JSON generation legitimately
    # takes minutes. Keep it separate from the general external-API timeout.
    LLM_TIMEOUT_SECONDS: float = float(get_env_variable("LLM_TIMEOUT_SECONDS", "300.0"))
    
    # HRSD ServiceNow LIVE URL
    SNOW_API_URL: str = get_env_variable("SNOW_API_URL", "https://mock.servicenow.com/api")
    
    # --- Advanced Timesheet AI Service (Retained from the latest user submission) ---
    TIMESHEET_HISTORICAL_WEEKS: int = int(get_env_variable("TIMESHEET_HISTORICAL_WEEKS", "12"))
    TIMESHEET_MAX_HOURS_OVERTIME_RISK: float = float(get_env_variable("TIMESHEET_MAX_HOURS_OVERTIME_RISK", "60.0"))
    TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD: float = float(get_env_variable("TIMESHEET_SCHEDULE_DEVIATION_THRESHOLD", "0.2"))
    TIMESHEET_HISTORICAL_DEVIATION_THRESHOLD: float = float(get_env_variable("TIMESHEET_HISTORICAL_DEVIATION_THRESHOLD", "0.3"))
    TIMESHEET_AUTO_APPROVE_SCORE: float = float(get_env_variable("TIMESHEET_AUTO_APPROVE_SCORE", "0.75"))
    TIMESHEET_REVIEW_REQUIRED_SCORE: float = float(get_env_variable("TIMESHEET_REVIEW_REQUIRED_SCORE", "0.4"))
    TIMESHEET_SCHEDULE_MATCH_WEIGHT: float = float(get_env_variable("TIMESHEET_SCHEDULE_MATCH_WEIGHT", "0.30"))
    TIMESHEET_OVERTIME_WEIGHT: float = float(get_env_variable("TIMESHEET_OVERTIME_WEIGHT", "0.40"))
    TIMESHEET_HISTORICAL_WEIGHT: float = float(get_env_variable("TIMESHEET_HISTORICAL_WEIGHT", "0.30"))
    
    # --- Hierarchical Enforcement & Microservice (Retained from the latest user submission) ---
    GLOBAL_MIN_AGE: int = int(get_env_variable("GLOBAL_MIN_AGE", "16"))
    GLOBAL_MAX_HOURS: int = int(get_env_variable("GLOBAL_MAX_HOURS", "60"))
    UK_MAX_HOURS: int = int(get_env_variable("UK_MAX_HOURS", "48"))
    UK_MIN_WAGE: float = float(get_env_variable("UK_MIN_WAGE", "11.44"))
    US_CA_MIN_WAGE: float = float(get_env_variable("US_CA_MIN_WAGE", "16.00"))
    POLICY_PRIORITY_LOW: int = int(get_env_variable("POLICY_PRIORITY_LOW", "50"))
    POLICY_PRIORITY_MEDIUM: int = int(get_env_variable("POLICY_PRIORITY_MEDIUM", "90"))
    POLICY_PRIORITY_HIGH: int = int(get_env_variable("POLICY_PRIORITY_HIGH", "100"))
    
    ENFORCEMENT_CACHE_TTL_SECONDS: int = int(get_env_variable("ENFORCEMENT_CACHE_TTL_SECONDS", "300"))
    ENFORCEMENT_TIME_TARGET_MS: float = float(get_env_variable("ENFORCEMENT_TIME_TARGET_MS", "5.0"))
    TEMPORAL_STALE_DAYS: int = int(get_env_variable("TEMPORAL_STALE_DAYS", "30"))
    ENFORCER_AGENT_ID: str = get_env_variable("ENFORCER_AGENT_ID", "RUNTIME_ENFORCER")
    
    # --- Ethical Agents (Retained from the latest user submission) ---
    PLR_HIGH_RISK_THRESHOLD: float = float(get_env_variable("PLR_HIGH_RISK_THRESHOLD", "0.8"))
    PLR_VULNERABILITIES: List[str] = get_env_variable("PLR_VULNERABILITIES", "Documentation Gap,Jurisdictional Conflict,Termination Audit Failure").split(',')
    SDFA_BIAS_SCORE: float = float(get_env_variable("SDFA_BIAS_SCORE", "0.01"))
    # HiRo encrypts PII with AES-256 (Fernet). Nothing here is ML-KEM or any
    # other post-quantum scheme, and claiming otherwise on a security card is a
    # compliance statement the product cannot back.
    SDFA_PQC_STATUS: str = get_env_variable("SDFA_PQC_STATUS", "AES-256 encryption (not post-quantum)")
    SDFA_TIME_PER_RECORD_MS: float = float(get_env_variable("SDFA_TIME_PER_RECORD_MS", "0.05"))
    ESA_FAIRNESS_SCORE: float = float(get_env_variable("ESA_FAIRNESS_SCORE", "0.98"))
    ESA_IMPACT_RATIO: float = float(get_env_variable("ESA_IMPACTC_RATIO", "1.02"))
    EOA_ONTOLOGY_VERSION: str = get_env_variable("EOA_ONTOLOGY_VERSION", "EOA-V4.1")
    SPA_REMOTE_SILO_RISK: float = float(get_env_variable("SPA_REMOTE_SILO_RISK", "0.75"))
    SPA_LOCAL_SILO_RISK: float = float(get_env_variable("SPA_LOCAL_SILO_RISK", "0.25"))
    SPA_REMOTE_ACTION: str = get_env_variable("SPA_REMOTE_ACTION", "Suggest cross-functional virtual coffee chats")
    SPA_LOCAL_ACTION: str = get_env_variable("SPA_LOCAL_ACTION", "Suggest team lunch")
    
    # --- General Agent constants (Retained from the latest user submission) ---
    BPMN_DEFAULT_START_NAME: str = get_env_variable("BPMN_DEFAULT_START_NAME", "Start Process")
    BPMN_DEFAULT_POLICY_CHECK_NAME: str = get_env_variable("BPMN_DEFAULT_POLICY_CHECK_NAME", "Policy Check")
    BPMN_DEFAULT_DECISION_NAME: str = get_env_variable("BPMN_DEFAULT_DECISION_NAME", "Conditions Met?")
    BPMN_DEFAULT_FINAL_APPROVAL_NAME: str = get_env_variable("BPMN_DEFAULT_FINAL_APPROVAL_NAME", "Final Approval")
    BPMN_DEFAULT_END_NAME: str = get_env_variable("BPMN_DEFAULT_END_NAME", "Process Complete")
    BPMN_SYSTEM_ASSIGNEE: str = get_env_variable("BPMN_SYSTEM_ASSIGNEE", "SYSTEM")
    BPMN_MANAGER_ASSIGNEE: str = get_env_variable("BPMN_MANAGER_ASSIGNEE", "MANAGER")
    BPMN_POLICY_CHECK_CONDITION: str = get_env_variable("BPMN_POLICY_CHECK_CONDITION", "IF Conditions")
    BPMN_ADMIN_ASSIGNEE: str = get_env_variable("BPMN_ADMIN_ASSIGNEE", "ADMIN")
    
    # --- Data Ingestion Agent (Retained from the latest user submission) ---
    INGESTION_FORMATS: List[str] = get_env_variable("INGESTION_FORMATS", "text/csv,application/json,text/plain").split(',')
    MAX_FILE_SIZE_MB: str = get_env_variable("MAX_FILE_SIZE_MB", "50")
    
    # --- PII Vault Mock Logic (Retained from the latest user submission) ---
    PII_MOCK_CIPHERTEXT_PREFIX: str = get_env_variable("PII_MOCK_CIPHERTEXT_PREFIX", "MOCK_CIPHER_FOR_")
    PII_POLICY_PAYROLL_PURPOSE: str = get_env_variable("PII_POLICY_PAYROLL_PURPOSE", "PAYROLL")
    PII_POLICY_ESS_PURPOSE: str = get_env_variable("PII_POLICY_ESS_PURPOSE", "ESS_PROFILE_ACCESS")
    PII_POLICY_ADMIN_ROLE_SUFFIX: str = get_env_variable("PII_POLICY_ADMIN_ROLE_SUFFIX", 'ADMIN')
    PII_POLICY_EMPLOYEE_ID_PREFIX: str = get_env_variable("PII_POLICY_EMPLOYEE_ID_PREFIX", 'EMP')
    
    # --- Dynamic Compliance Engine (Retained from the latest user submission) ---
    REGULATORY_FEED_URL: str = get_env_variable("REGULATORY_FEED_URL", "http://mock-regulatory-service:8080/feed")
    DEFAULT_GLOBAL_SCORE: int = int(get_env_variable("DEFAULT_GLOBAL_SCORE", "88"))
    MOCK_BASE_ALERTS: int = int(get_env_variable("MOCK_BASE_ALERTS", "15"))
    POLICY_SCRAPING_JURISDICTIONS: List[str] = get_env_variable("POLICY_SCRAPING_JURISDICTIONS", "US-CA,UK-EN,DE-BW").split(',')
    
    # CRITICAL PRODUCTION FLAGS
    ENABLE_MOCK_REGULATORY_FEEDS: bool = get_env_variable("ENABLE_MOCK_REGULATORY_FEEDS", "false").lower() == "true" # Must be False in true production
    ENABLE_POLICY_SCRAPING: bool = get_env_variable("ENABLE_POLICY_SCRAPING", "true").lower() == "true" # Enabled by default

    # --- SI INTEGRATION: NEW STREAMING & WEB SOCKET CONFIGURATION (Retained from the latest user submission) ---
    STREAMING_CHUNK_SIZE: int = int(get_env_variable("STREAMING_CHUNK_SIZE", "1024"))
    WEBSOCKET_PING_INTERVAL: int = int(get_env_variable("WEBSOCKET_PING_INTERVAL", "30"))
    WEBSOCKET_MAX_CONNECTIONS: int = int(get_env_variable("WEBSOCKET_MAX_CONNECTIONS", "100"))
    TELEMETRY_UPDATE_INTERVAL_SECONDS: int = int(get_env_variable("TELEMETRY_UPDATE_INTERVAL_SECONDS", "2"))
    STREAMING_TIMEOUT_SECONDS: int = int(get_env_variable("STREAMING_TIMEOUT_SECONDS", "300"))
    
    # --- SI INTEGRATION: SIMULATION CONFIGURATION (Retained from the latest user submission) ---
    SIMULATION_MAX_WORKERS: int = int(get_env_variable("SIMULATION_MAX_WORKERS", "10"))
    SIMULATION_TIMEOUT_SECONDS: int = int(get_env_variable("SIMULATION_TIMEOUT_SECONDS", "30"))
    WHAT_IF_CACHE_TTL_SECONDS: int = int(get_env_variable("WHAT_IF_CACHE_TTL_SECONDS", "300"))
    SYNTHETIC_DATA_GENERATION_ENABLED: bool = get_env_variable("SYNTHETIC_DATA_GENERATION_ENABLED", "true").lower() == "true"
    MAX_SYNTHETIC_RECORDS: int = int(get_env_variable("MAX_SYNTHETIC_RECORDS", "10000"))
    
    # --- SI INTEGRATION: REMEDIATION CONFIGURATION (Retained from the latest user submission) ---
    REMEDIATION_MAX_ATTEMPTS: int = int(get_env_variable("REMEDIATION_MAX_ATTEMPTS", "3"))
    REMEDIATION_AUTO_APPLY: bool = get_env_variable("REMEDIATION_AUTO_APPLY", "false").lower() == "true"
    REMEDIATION_AI_MODEL: str = get_env_variable("REMEDIATION_AI_MODEL", "qwen2.5:7b")
    REMEDIATION_TIMEOUT_SECONDS: int = int(get_env_variable("REMEDIATION_TIMEOUT_SECONDS", "60"))
    
    # --- SI INTEGRATION: REAL-TIME MONITORING (Retained from the latest user submission) ---
    ENABLE_LIVE_TELEMETRY: bool = get_env_variable("ENABLE_LIVE_TELEMETRY", "true").lower() == "true"
    TELEMETRY_RETENTION_DAYS: int = int(get_env_variable("TELEMETRY_RETENTION_DAYS", "30"))
    METRICS_UPDATE_INTERVAL_SECONDS: int = int(get_env_variable("METRICS_UPDATE_INTERVAL_SECONDS", "5"))
    
    # --- SI INTEGRATION: SELF-CORRECTING AGENT (Retained from the latest user submission) ---
    SELF_CORRECTING_MAX_ITERATIONS: int = int(get_env_variable("SELF_CORRECTING_MAX_ITERATIONS", "5"))
    AGENT_SANDBOX_ENABLED: bool = get_env_variable("AGENT_SANDBOX_ENABLED", "true").lower() == "true"
    AGENT_VALIDATION_TIMEOUT_SECONDS: int = int(get_env_variable("AGENT_VALIDATION_TIMEOUT_SECONDS", "30"))
    
    # --- SI INTEGRATION: CACHE CONFIGURATION (Retained from the latest user submission) ---
    REDIS_CACHE_ENABLED: bool = get_env_variable("REDIS_CACHE_ENABLED", "true").lower() == "true"
    CACHE_DEFAULT_TTL: int = int(get_env_variable("CACHE_DEFAULT_TTL", "300"))
    SIMULATION_CACHE_TTL: int = int(get_env_variable("SIMULATION_CACHE_TTL", "600"))
    
    # --- SI INTEGRATION: FRONTEND CONFIGURATION (Retained from the latest user submission) ---
    FRONTEND_API_BASE_URL: str = get_env_variable("FRONTEND_API_BASE_URL", "http://localhost:3000")
    ENABLE_CORS: bool = get_env_variable("ENABLE_CORS", "true").lower() == "true"
    CORS_ALLOWED_ORIGINS: List[str] = get_env_variable("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    
    # --- SI INTEGRATION: PERFORMANCE CONFIGURATION (Retained from the latest user submission) ---
    MAX_CONCURRENT_SIMULATIONS: int = int(get_env_variable("MAX_CONCURRENT_SIMULATIONS", "5"))
    MAX_CONCURRENT_STREAMS: int = int(get_env_variable("MAX_CONCURRENT_STREAMS", "10"))
    REQUEST_TIMEOUT_SECONDS: int = int(get_env_variable("REQUEST_TIMEOUT_SECONDS", "30"))
    
    # --- SI INTEGRATION: SECURITY CONFIGURATION (Retained from the latest user submission) ---
    ENABLE_RATE_LIMITING: bool = get_env_variable("ENABLE_RATE_LIMITING", "true").lower() == "true"
    # High default so bulk data initialization and heavy load do not trip the
    # limiter; override per environment as needed.
    RATE_LIMIT_PER_MINUTE: int = int(get_env_variable("RATE_LIMIT_PER_MINUTE", "3000"))
    ENABLE_JWT_AUTH: bool = get_env_variable("ENABLE_JWT_AUTH", "true").lower() == "true"
    
    # --- SI INTEGRATION: LOGGING CONFIGURATION (Retained from the latest user submission) ---
    ENABLE_STRUCTURED_LOGGING: bool = get_env_variable("ENABLE_STRUCTURED_LOGGING", "true").lower() == "true"
    LOG_JSON_FORMAT: bool = get_env_variable("LOG_JSON_FORMAT", "true").lower() == "true"
    SENTRY_DSN: str = get_env_variable("SENTRY_DSN", "")
    
    # --- SI INTEGRATION: TESTING & DEVELOPMENT (Retained from the latest user submission) ---
    ENABLE_MOCK_MODE: bool = get_env_variable("ENABLE_MOCK_MODE", "false").lower() == "true"
    MOCK_AI_RESPONSES: bool = get_env_variable("MOCK_AI_RESPONSES", "false").lower() == "true"
    DEBUG_MODE: bool = get_env_variable("DEBUG_MODE", "false").lower() == "true"

settings = Settings()
