# backend/app_lifespan.py
"""FastAPI lifespan manager and background tasks for the HiRo backend.

Separated from server.py (which assembles the app and mounts routers). The
lifespan wires every service onto app.state on startup and tears them down on
shutdown; the background tasks are the telemetry and policy-scraping loops it
launches.
"""
import logging
import asyncio
import psutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI

try:
    import redis.asyncio as redis_async
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis_async = None

from config.settings import settings

from services.postgres_client import pg_client
from services.event_publisher_service import EventPublisherService
from services.auth_service import AuthService
from services.admin_service import AdminService
from services.ai_services import AIService
from services.pqc_pii_layer import PQCEncryptionWrapper
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
from services.policy_scraping_agent import PolicyScrapingAgent, AHCMGovernanceChaincode
from services.internal_mock_api import InternalMockAPI
from services.configuration_agent import ConfigurationAgent
from services.workforce_planning_service import WorkforcePlanningService
from services.talent_acquisition_service import TalentAcquisitionService
from routes.streaming_routes import manager as websocket_manager

logger = logging.getLogger("hiro.server")


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
            
async def run_policy_scraping_background(policy_scraping_agent: PolicyScrapingAgent):
    """Starts the continuous global sentinel monitoring loop."""
    logger.info(" 🌐 Starting Policy Scraping Agent (Global Sentinel) monitoring...")
    try:
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
        # 1. MongoDB. A failed connection is non-fatal: auth falls back to an
        # in-memory store for the built-in accounts (see AuthService), and the
        # rest of the stack already degrades gracefully when a datastore is down.
        logger.info("Connecting to MongoDB...")
        try:
            app.state.mongo_client = AsyncIOMotorClient(
                settings.mongo_url(), serverSelectionTimeoutMS=2000)
            await app.state.mongo_client.admin.command('ping')
            logger.info(" ✅  MongoDB connected")
        except Exception as e:
            logger.warning(f" ⚠️  MongoDB unavailable: {e}")
            app.state.mongo_client = None
                
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
        
        app.state.wfm_service = WorkforcePlanningService(
            publisher=app.state.event_publisher, mongo_client=app.state.mongo_client)
        app.state.ta_service = TalentAcquisitionService(publisher=app.state.event_publisher)

        # ESS/MSS services power the Employee and Manager self-service portals.
        from services.ess_service import ESSService
        from services.mss_service import MSSService
        app.state.ess_service = ESSService(publisher=app.state.event_publisher)
        app.state.mss_service = MSSService(publisher=app.state.event_publisher)

        
        app.state.digital_twin_agent = DigitalTwinAgent(
            publisher=app.state.event_publisher, 
            ai_service=app.state.ai_service,
            wfm_service=app.state.wfm_service, 
            ta_service=app.state.ta_service    
        )
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

