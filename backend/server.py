# /backend/server.py — HiRo Enterprise API Server
import os
import sys 
import logging
import json
import asyncio
import uuid
import psutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Union, Optional

# --- Setup Paths and Environment ---
THIS_FILE = Path(__file__).resolve()
ROOT_DIR = THIS_FILE.parent
BACKEND_DIR = ROOT_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    # CRITICAL FIX: Corrected the redundant 'sys.' prefix
    sys.path.insert(0, str(BACKEND_DIR)) 

# Load environment variables
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

# Import FastAPI and dependencies
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends, status, Response, Form, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.gzip import GZipMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

# SI INTEGRATION: Import WebSocket and streaming dependencies
from fastapi.websockets import WebSocket, WebSocketDisconnect
import websockets

# Conditional imports for Redistry:
try:
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis_async = None

# Import settings
from config.settings import settings

# Import Pydantic models (with fallback if schema file is missing/refactoring)
try:
    from services.schemas.models import (
        UserDetails, 
        LoginRequest as SchemaLoginRequest,  
        LoginResponse as SchemaLoginResponse, 
        AuthPayload as SchemaAuthPayload,
        ConfigurationUpdate
    )
except ImportError:
    class UserDetails(BaseModel):
        id: Optional[str] = None
        user_id: Optional[str] = None
        username: str
        email: str
        full_name: str
        role: str
        is_active: bool
        created_at: str
    class SchemaLoginRequest(BaseModel):
        username: str
        password: str
    class SchemaLoginResponse(BaseModel):
        access_token: str
        token_type: str
        user: UserDetails
    class SchemaAuthPayload(BaseModel):
        sub: str
        role: str
        user_id: str
        email: str
    class ConfigurationUpdate(BaseModel):
        key: str
        value: Any
        applied_by: str


# --- Logging Setup ---
log_dir = ROOT_DIR / 'logs'
log_dir.mkdir(exist_ok=True)
logging.basicConfig( 
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / 'server.log', encoding='utf-8')
    ])
logger = logging.getLogger("hiro.server")

# --- Service Imports (Ensure all agents are explicitly imported here) ---
try:
    from services.postgres_client import pg_client 
    from services.event_publisher_service import EventPublisherService
    from services.auth_service import AuthService
    from services.admin_service import AdminService
    from services.auth_deps import get_auth_payload
    from services.comprehensive_routes import ALL_ROUTERS
    from services.middleware.rate_limit_middleware import RateLimitMiddleware  
    from services.ai_services import AIService
    from services.pqc_pii_layer import PQCEncryptionWrapper        

    # SI Integration Agents (Explicit Imports)
    from services.self_correcting_agent import SelfCorrectingAgent
    from services.synthetic_twin_engine import SyntheticTwinEngine
    from services.cognitive_remediation_agent import CognitiveRemediationAgent        
    from services.digital_twin_agent import DigitalTwinAgent        
    from services.agent_creation_service import AgentCreationService
    from services.hr_modules import HRModulesService
    from services.policy_versioning import PolicyVersioningService
    from services.vv_compiler import VVCompiler
    from services.multi_agent_hrsd import MultiAgentHRSDSystem
    from services.external_api_connector import ExternalAPIConnector 
    
    # Deployment Cycle Dependencies
    from services.policy_scraping_agent import PolicyScrapingAgent, AHCMGovernanceChaincode 
    from services.internal_mock_api import InternalMockAPI 
    from services.configuration_agent import ConfigurationAgent 

    # CRITICAL FIX: Import missing services required by DTLA
    from services.workforce_planning_service import WorkforcePlanningService 
    from services.talent_acquisition_service import TalentAcquisitionService 

    # WebSocket Manager 
    from routes.streaming_routes import manager as websocket_manager
except ImportError as e:
    logger.critical(f"Failed to import services/dependencies: {e}. Cannot start.")
    raise

# --- Background Tasks ---
async def generate_telemetry_background(publisher: EventPublisherService):
    """Background task to generate regular telemetry updates for the dashboard."""
    import random
        
    try:
        psutil.cpu_percent(interval=None)
    except Exception as e:
        logger.warning(f"Initial psutil call failed: {e}")
            
    while True:
        try:
            await asyncio.sleep(settings.TELEMETRY_UPDATE_INTERVAL_SECONDS)         
                        
            # The WebSocket push below needs no message bus. This used to skip
            # the whole loop body when NATS was down, so the live telemetry panel
            # subscribed successfully and then received nothing at all, with no
            # sign anywhere that it had been switched off.
            bus_up = bool(publisher and getattr(getattr(publisher, "nc", None), "is_connected", False))

            
            # Measure real system metrics (and the time it takes to collect them).
            loop = asyncio.get_event_loop()
            _t0 = loop.time()
            cpu_load = psutil.cpu_percent(interval=None)
            memory_load = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            active_conns = len(getattr(websocket_manager, 'active_connections', {}) or {})
            subscribers = len(getattr(websocket_manager, 'telemetry_subscribers', set()) or set())
            collect_latency_ms = (loop.time() - _t0) * 1000.0
            interval = max(settings.TELEMETRY_UPDATE_INTERVAL_SECONDS, 0.001)
            # Real fan-out rate: telemetry messages pushed to subscribers per second.
            events_per_second = subscribers / interval

            telemetry_data = {
                # Field names the frontend telemetry consumers expect (real values).
                "cpu_load": round(cpu_load, 1),
                "memory_load": round(memory_load, 1),
                "disk_usage": round(disk_usage, 1),
                "active_nodes": active_conns,
                "events_per_second": round(events_per_second, 2),
                "latency": round(collect_latency_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
                        
            # Always push to the connected browsers; publish to the bus only if
            # there is one.
            if bus_up:
                await publisher.publish_telemetry_metrics(telemetry_data)
            await websocket_manager.broadcast_telemetry(telemetry_data)
                
        except Exception as e: 
            logger.error(f"Telemetry generation error: {e}")
            await asyncio.sleep(5)
            
# CRITICAL FIX 2: Background task for Policy Scraping Agent
async def run_policy_scraping_background(policy_scraping_agent: PolicyScrapingAgent):
    """Starts the continuous global sentinel monitoring loop."""
    logger.info(" 🌐 Starting Policy Scraping Agent (Global Sentinel) monitoring...")
    try:
        # CRITICAL FIX: Call the task-driven method (execute_full_sweep) inside an eternal loop 
        # to restore background monitoring functionality.
        if hasattr(policy_scraping_agent, 'monitor_and_generate_rules'):
            await policy_scraping_agent.monitor_and_generate_rules()
        else:
            logger.error("Policy Scraping Agent instance lacks 'monitor_and_generate_rules' method.")
            
    except Exception as e:
        logger.error(f"Policy Scraping Agent crashed: {e}")
        
# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    logger.info(" 🚀  Starting HiRo backend server with SI Integration...")

    # 0. Refuse to boot in production with a known or weak secret.
    #
    # This used to check two hardcoded literals against two settings. It let
    # through every value committed to the repo's own .env -- which is the
    # single most likely thing to be running in production by accident -- and it
    # never looked at PII_SALT at all, the value the entire PII encryption key is
    # derived from.
    _KNOWN_SECRETS = {
        # settings.py defaults
        "hiro_production_signing_key_secure_48char",
        "hiro_zero_trust_production_key_1001001",
        "default_pii_salt_4096_secure",
        # values committed to .env in this repository
        "hiro_pii_salt_dev_2026_min32chars_xK9mP2qR",
        "hiro_jwt_dev_2026_minimum_64_chars_secure_random_wX7nQ4vB8mK1pL3jH6dF9sA2cE5tR0yU",
        "hiro_agent_dev_2026_zero_trust_secret_mN4kW7xP",
    }
    _MIN_SECRET_LEN = 32
    if settings.ENV in ("production", "prod"):
        problems = []
        for name in ("JWT_SECRET_KEY", "AGENT_SIGNING_SECRET", "PII_SALT"):
            value = getattr(settings, name).get_secret_value()
            if value in _KNOWN_SECRETS:
                problems.append(f"{name} is a value published in this repository")
            elif len(value) < _MIN_SECRET_LEN:
                problems.append(f"{name} is only {len(value)} characters "
                                f"(minimum {_MIN_SECRET_LEN})")
        if problems:
            raise RuntimeError(
                "Refusing to start in production: " + "; ".join(problems) + ". "
                "Set JWT_SECRET_KEY, AGENT_SIGNING_SECRET and PII_SALT to strong unique "
                "values of at least 32 characters. Note that changing PII_SALT changes "
                "the PII encryption key, so existing encrypted data must be migrated first."
            )

    try:
        # 1. MongoDB
        logger.info("Connecting to MongoDB...")
        app.state.mongo_client = AsyncIOMotorClient(settings.mongo_url())
        await app.state.mongo_client.admin.command('ping')
        logger.info(" ✅  MongoDB connected")
                
        # 2. PostgreSQL
        try:
            await pg_client.connect(settings.postgres_url())     
            app.state.pg_client = pg_client                         
            logger.info(" ✅  PostgreSQL connected")
        except Exception as e:        
            logger.error(f" ❌  PostgreSQL connection failed: {e}")
            
        # 3. PII encryption key initialisation (AES-256, derived from PII_SALT)
        app.state.pqc_wrapper = PQCEncryptionWrapper.get_instance()    
        await app.state.pqc_wrapper.initialize_keys()
        logger.info(" ✅  PII encryption wrapper initialised (AES-256)")
        
        # 4. Core AI Services
        app.state.ai_service = AIService()
        logger.info(" ✅  AI service initialized")
                
        # 5. Event Publisher (NATS)
        app.state.event_publisher = EventPublisherService(agent_id="OrchestratorKernel")   
        nats_connected = False
        try:
            await app.state.event_publisher.connect(settings.NATS_URL)
            logger.info(" ✅  Event publisher connected")
            nats_connected = True
        except Exception as e:
            logger.warning(f" ⚠️  Event publisher connection failed: {e}")          
                
        # 6. Auth Service & Test Users
        app.state.auth_service = AuthService(app.state.mongo_client)
        await app.state.auth_service.initialize_test_users()
        logger.info(" ✅  Test users initialized (admin, hritmanager, manager, employee, hrbp)")

        # 7. Core Services Initialization (Dependency Injection)
        app.state.internal_mock_api = InternalMockAPI() # Initialize Mock API for fallbacks
        
        # CRITICAL FIX 3: Conditionally set the mock API instance based on settings
        if settings.ENABLE_MOCK_REGULATORY_FEEDS:
            mock_api_instance = app.state.internal_mock_api
            logger.warning(" ⚠️  POLICY SCRAPING: Using MOCK regulatory feeds.")
        else:
            mock_api_instance = None
            logger.info(" ✅  POLICY SCRAPING: Using LIVE regulatory feeds.")
            
        app.state.external_api_connector = ExternalAPIConnector(internal_mock_api=mock_api_instance)
        
        app.state.policy_versioning_service = PolicyVersioningService()
        app.state.vv_compiler = VVCompiler()
        app.state.admin_service = AdminService(app.state.mongo_client, app.state.pg_client)
        
        # 8. Agent Initialization (Full dependency wiring)
        
        # FIX START: Initialize the missing dependency services FIRST
        app.state.wfm_service = WorkforcePlanningService(
            publisher=app.state.event_publisher, mongo_client=app.state.mongo_client)
        app.state.ta_service = TalentAcquisitionService(publisher=app.state.event_publisher)

        # ESS/MSS services power the Employee and Manager self-service portals.
        from services.ess_service import ESSService
        from services.mss_service import MSSService
        app.state.ess_service = ESSService(publisher=app.state.event_publisher)
        app.state.mss_service = MSSService(publisher=app.state.event_publisher)

        # FIX END
        
        # CRITICAL FIX 4: Correctly inject WFMService and TAService into DigitalTwinAgent (Fixed in previous step by class replacement)
        app.state.digital_twin_agent = DigitalTwinAgent(
            publisher=app.state.event_publisher, 
            ai_service=app.state.ai_service,
            wfm_service=app.state.wfm_service, 
            ta_service=app.state.ta_service    
        )
        # CRITICAL FIX 5: Inject DigitalTwinAgent instance into SyntheticTwinEngine
        app.state.synthetic_twin_engine = SyntheticTwinEngine(
            dt_agent=app.state.digital_twin_agent, 
            ai_service=app.state.ai_service
        )
        
        app.state.self_correcting_agent = SelfCorrectingAgent(app.state.ai_service)
        
        # AutonomousUpgradeAgent and TestAutomationAgent are gone: both were
        # coin-flip-and-sleep stubs that wrote fabricated DEPLOYED/PASSED rows.
        app.state.configuration_agent = ConfigurationAgent(
            ai_service=app.state.ai_service, 
            publisher=app.state.event_publisher,
            policy_versioning_service=app.state.policy_versioning_service,
            vv_compiler=app.state.vv_compiler,
        )
        app.state.agent_creation_service = AgentCreationService(
            ai_service=app.state.ai_service,
            publisher=app.state.event_publisher,
            pg_client_instance=app.state.pg_client
        )
        
        # Mongo backs the user directory, which is the electorate DAO quorum is
        # measured against.
        app.state.governance_chaincode = AHCMGovernanceChaincode(mongo_client=app.state.mongo_client)
        app.state.policy_scraping_agent = PolicyScrapingAgent(
            governance_chaincode=app.state.governance_chaincode,
            ai_service=app.state.ai_service,
            api_connector=app.state.external_api_connector,
            policy_versioning_service=app.state.policy_versioning_service,
            publisher=app.state.event_publisher,
            vv_compiler=app.state.vv_compiler # Added VV Compiler injection for sentinel flow robustness
        )

        app.state.hr_modules_service = HRModulesService(app.state.mongo_client, app.state.event_publisher)

        # Notifications are what tell a person their request was decided.
        from services import notification_service
        await notification_service.ensure_table()
        app.state.hrsd_system = MultiAgentHRSDSystem(
            ai_service=app.state.ai_service,
            hr_modules_service=app.state.hr_modules_service,
            publisher=app.state.event_publisher
        )
        app.state.cognitive_remediation_agent = CognitiveRemediationAgent(app.state.ai_service)

        # Services the API routes depend on that were previously never attached
        # to app.state (their endpoints 503'd or fell back to stubs).
        from services.xai_wrapper import XAIWrapper
        from services.immersive_learning_agent import ImmersiveLearningAgent
        from services.bpel_agent import BPELAgent
        from services.rlff_llm_fine_tuner import RLFFLLMFineTuner
        app.state.xai_wrapper = XAIWrapper()
        app.state.immersive_learning_agent = ImmersiveLearningAgent(
            pub=app.state.event_publisher, ai=app.state.ai_service
        )
        app.state.bpel_agent = BPELAgent(
            ai_service=app.state.ai_service,
            policy_versioning_service=app.state.policy_versioning_service,
        )
        app.state.rlff_llm_fine_tuner = RLFFLLMFineTuner(
            ai_service=app.state.ai_service, publisher=app.state.event_publisher
        )
        # Alias so handlers that look up `talent_acquisition_service` resolve too.
        app.state.talent_acquisition_service = app.state.ta_service
        logger.info(" ✅  All HiRo SI Agents initialized and wired.")
                
        # 9. Start Background Tasks
        app.state.telemetry_task = None
        app.state.policy_scraping_task = None
        
        if nats_connected:        
            if settings.ENABLE_LIVE_TELEMETRY:
                app.state.telemetry_task = asyncio.create_task(generate_telemetry_background(app.state.event_publisher))
                logger.info(" ✅  Telemetry generation started")

            if settings.ENABLE_POLICY_SCRAPING: 
                app.state.policy_scraping_task = asyncio.create_task(run_policy_scraping_background(app.state.policy_scraping_agent))
                logger.info(" ✅  Policy Scraping Agent (Global Sentinel) started")
        
        # 10. Redis
        if REDIS_AVAILABLE:
            try:
                app.state.redis_client = redis_async.from_url(settings.redis_url())
                await app.state.redis_client.ping()
                logger.info(" ✅  Redis connected")
            except Exception as e:
                logger.warning(f" ⚠️  Redis connection failed: {e}")
                app.state.redis_client = None
        else:
            app.state.redis_client = None
                
        logger.info(f" ✅  HiRo backend ready. Log level: {settings.LOG_LEVEL}")
                
        yield 
        
    except Exception as e:
        logger.critical(f" ❌  HiRo startup failed: {e}", exc_info=True)
        yield 
            
    # SHUTDOWN
    logger.info(" 🛑  Shutting down HiRo backend...")
        
    if hasattr(app.state, "telemetry_task") and app.state.telemetry_task:
        app.state.telemetry_task.cancel() 
        
    if hasattr(app.state, "policy_scraping_task") and app.state.policy_scraping_task:
        app.state.policy_scraping_task.cancel()
        if hasattr(app.state.policy_scraping_agent, 'is_running'):
            app.state.policy_scraping_agent.is_running = False 
            logger.info("Policy Scraping Agent monitoring stopped.")
    
    # CRITICAL FIX 6: Stop Digital Twin Monitoring Gracefully
    if hasattr(app.state, 'digital_twin_agent') and hasattr(app.state.digital_twin_agent, 'stop_monitoring'):
        try:
            # This relies on the fixed DigitalTwinAgent class having a robust stop_monitoring method
            await app.state.digital_twin_agent.stop_monitoring()
            logger.info("Digital Twin Agent monitoring stopped.")
        except Exception as e:
            logger.error(f"Error stopping Digital Twin Agent: {e}")
            
    try:        
        if hasattr(app.state, "mongo_client") and app.state.mongo_client:
            app.state.mongo_client.close()
            logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB: {e}")
        
    try:
        if hasattr(app.state, "event_publisher") and app.state.event_publisher:
            await app.state.event_publisher.close()
            logger.info("Event publisher closed")
    except Exception as e:   
        logger.error(f"Error closing Event Publisher: {e}")
        
    try:
        from services.postgres_client import pg_client as _pg_client_global 
        if _pg_client_global and hasattr(_pg_client_global, 'close'):
            await _pg_client_global.close()
            logger.info("PostgreSQL connection closed")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL: {e}")
        
    logger.info(" ✅  Shutdown complete")

# --- App Definition ---
app = FastAPI(  
    title="HiRo Enterprise API",
    version="5.0.0",
    description="AI-Powered HR Management Platform with Synthetic Intelligence",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.LOG_LEVEL.upper() == "DEBUG" else None,
    redoc_url="/api/redoc" if settings.LOG_LEVEL.upper() == "DEBUG" else None,
    openapi_url="/api/openapi.json" if settings.LOG_LEVEL.upper() == "DEBUG" else None
)

# --- Middleware ---
if settings.ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", 
        "OPTIONS", "PATCH", "HEAD"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600
    )
app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- Security headers (applied to every response) ---
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",  # modern guidance: disable legacy auditor, rely on CSP
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",  # JSON API only
}

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    # HSTS only in production (avoids pinning HTTPS during local http dev)
    if not settings.DEBUG_MODE:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
        )
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:12]
    start_time = datetime.now()
        
    logger.info(f" 📥  Request [{request_id}]: {request.method} {request.url.path}")
        
    try:
        response = await call_next(request)
        duration = (datetime.now() - start_time).total_seconds() * 1000      
        logger.info(f" 📤  Response [{request_id}]: {response.status_code} ({duration:.2f}ms)")
        return response
        
    except HTTPException as http_exc:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.warning(f" ⚠️  HTTP Error [{request_id}]: {http_exc.status_code} - {http_exc.detail} ({duration:.2f}ms)")
        raise
        
    except Exception as exc:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f" ❌  Server Error [{request_id}]: {str(exc)} ({duration:.2f}ms)", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})

if settings.ENABLE_RATE_LIMITING:
    max_body_size_bytes = int(float(settings.MAX_BODY_SIZE_MB) * 1024 * 1024)
    app.add_middleware(RateLimitMiddleware,
                       requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
                       max_body_size=max_body_size_bytes)

# --- Router Setup ---
api = APIRouter()

@api.get("/", include_in_schema=False)
async def root():
    return PlainTextResponse("HiRo API Server is running")

# --- Health Endpoints (API V1) ---
@api.get("/health")
async def health():
    """Health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "hiro-api",
        "version": "5.0.0"
    }

@api.get("/health/detailed")
async def health_detailed(request: Request):
    """Detailed health check with service status"""
    services = {}
        
    # Check Mongo
    try:
        if hasattr(request.app.state, "mongo_client"):
            await request.app.state.mongo_client.admin.command('ping')       
            services["mongodb"] = {"status": "healthy"}
        else:
            services["mongodb"] = {"status": "not_initialized"}
    except Exception as e:
        services["mongodb"] = {"status": "unhealthy", "error": str(e)}
        
    # Check Postgres
    try:
        from services.postgres_client import pg_client as _pg_client 
        if hasattr(_pg_client, 'is_connected') and _pg_client.is_connected:         
            services["postgresql"] = {"status": "healthy"}
        else:
            services["postgresql"] = {"status": "disconnected"}
    except Exception as e:
        services["postgresql"] = {"status": "unhealthy", "error": str(e)}
        
    # Check SI Services
    services["si_services"] = {
        "self_correcting_agent": "active" if hasattr(request.app.state, "self_correcting_agent") else "inactive",
        "synthetic_twin_engine": "active" if hasattr(request.app.state, "synthetic_twin_engine") else "inactive",
        "pqc_wrapper": "active" if hasattr(request.app.state, "pqc_wrapper") and request.app.state.pqc_wrapper.master_key_bytes else "inactive" 
    }  
        
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services
    }

# --- Auth Endpoints ---
@api.post("/auth/login", response_model=SchemaLoginResponse) 
async def login_user(request: Request):
    """Authenticate user and return JWT token"""
    try:
        content_type = request.headers.get("content-type", "").lower()
        username = None
        password = None 
        
        if "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            username = form_data.get("username")
            password = form_data.get("password")
        else:
            try:
                json_data = await request.json()        
                username = json_data.get("username")
                password = json_data.get("password")
            except:
                pass
                
        if not username or not password:
            raise HTTPException(status_code=422, detail="Username and password are required") 
            
        logger.info(f"HiRo login attempt for user: {username}")
                
        auth_service = request.app.state.auth_service
        user = await auth_service.authenticate_user(username, password)
                
        if not user:
            logger.warning(f"Failed login attempt for user: {username}")
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials" 
            )
                
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")
                
        user_id_str = str(user.get("_id", "")) if user.get("_id") else user.get("username", "") 
        user_response = {
            "id": user_id_str,
            "user_id": user_id_str,
            "username": user.get("username", ""),
            "email": user.get("email", ""),
            "full_name": user.get("full_name", ""),
            "role": user.get("role", "employee"),
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at", datetime.now(timezone.utc).isoformat())
        }
        
        access_token = auth_service.create_access_token(
            data={
                "sub": user["username"],
                "role": user["role"],
                "user_id": user_id_str,
                "email": user.get("email", ""),
                "employee_uuid": user.get("employee_uuid"),
            },
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        )
                
        return SchemaLoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserDetails(**user_response)
        )
        
    except HTTPException:      
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during login")

@api.get("/auth/test-users")
async def get_test_users(request: Request):
    """Get information about available test users"""
    try:
        auth_service = request.app.state.auth_service
        test_users = []
        for username in ["admin", "hritmanager", "hrbp", "manager", "employee"]: 
            user = await auth_service.get_user_by_username(username)
            if user:
                test_users.append({
                    "username": user.get("username"),
                    "role": user.get("role"),
                    "full_name": user.get("full_name"),       
                    "portals": user.get("portals", [])
                })
        return {"test_users": test_users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api.post("/auth/logout")
async def logout_user(request: Request, payload: SchemaAuthPayload = Depends(get_auth_payload)):
    return {"message": "Logout successful"}

@api.get("/me", response_model=UserDetails)
async def get_current_user(request: Request, payload: SchemaAuthPayload = Depends(get_auth_payload)):
    try:
        auth_service = request.app.state.auth_service      
        user = await auth_service.get_user_by_username(payload.sub)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
                
        user_id_str = str(user.get("_id", "")) if user.get("_id") else user.get("username", "") 
        return UserDetails(
            id=user_id_str,
            user_id=user_id_str,
            username=user.get("username", ""),
            email=user.get("email", ""),
            full_name=user.get("full_name", ""),
            role=user.get("role", "employee"),
            is_active=user.get("is_active", True),
            created_at=user.get("created_at", datetime.now(timezone.utc).isoformat())
        )
    except HTTPException:        
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching user details")

# --- Include Service Routers ---
try:
    from services.comprehensive_routes import ALL_ROUTERS
    for router in ALL_ROUTERS:
        api.include_router(router)
except ImportError:
    pass

# --- People lifecycle routers ---
from routes.people_lifecycle_routes import PEOPLE_LIFECYCLE_ROUTERS
for router in PEOPLE_LIFECYCLE_ROUTERS:
    api.include_router(router)

# --- Talent intelligence routers ---
try:
    from routes.talent_routes import TALENT_ROUTERS
    for router in TALENT_ROUTERS:
        api.include_router(router)
except ImportError as e:
    logger.warning(f"Talent intelligence routers unavailable: {e}")

app.include_router(api, prefix="/api")

# =========================================================================
# CRITICAL FIX: ROOT HEALTH CHECK FOR DOCKER
# =========================================================================
@app.get("/health")
async def root_health():
    """
    Root health check that matches Docker Healthcheck configuration
    """
    return {
        "status": "healthy",
        "service": "hiro-backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# =========================================================================
# --- Global Exception Handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# --- WebSocket & Streaming ---
@app.websocket("/ws/si-integration")
async def websocket_si_integration(websocket: WebSocket, client_id: str = "anonymous"):
    """WebSocket endpoint for SI integration real-time communication"""
    await websocket_manager.connect(websocket, client_id)
        
    try:
        await websocket.send_json({  
            "type": "connection_established",
            "client_id": client_id,
            "message": "Connected to SI Integration WebSocket",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
                
        while True:
            try:         
                data = await websocket.receive_text()
                message = json.loads(data)
                                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": message.get("timestamp")}) 
                elif message.get("type") == "subscribe_telemetry":
                    websocket_manager.subscribe_telemetry(client_id)
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "channel": "telemetry",   
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                elif message.get("type") == "request_simulation":
                    # NOTE: Simulation request is now handled by the REST API, 
                    # but this remains for future real-time simulation status updates.
                    simulation_id = message.get("simulation_id")                 
                    await websocket.send_json({
                        "type": "simulation_started",
                        "simulation_id": simulation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }) 
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_json({"type": "error", "message": str(e)})
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}") 
    finally:
        websocket_manager.disconnect(client_id)
        logger.info(f"Client {client_id} disconnected from SI WebSocket")

# The duplicate /stream/agent-thoughts endpoint is removed as it's included via ALL_ROUTERS -> streaming_routes.py

# --- AI knowledge routers ---
from routes.ai_knowledge_routes import ALL_AI_KNOWLEDGE_ROUTERS
for _ai_knowledge_router in ALL_AI_KNOWLEDGE_ROUTERS:
    app.include_router(_ai_knowledge_router, prefix="/api")

# CRITICAL FIX: Include the standard Python execution block for local development
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server in development mode...")
    # Using app:app to support the lifespan management in uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)