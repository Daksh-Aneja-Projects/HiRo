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

# --- Service Imports (only what server.py itself references; the lifespan wires
# the rest in app_lifespan.py). ---
try:
    from services.postgres_client import pg_client
    from services.auth_deps import get_auth_payload
    from services.comprehensive_routes import ALL_ROUTERS
    from services.middleware.rate_limit_middleware import RateLimitMiddleware
    from routes.streaming_routes import manager as websocket_manager
except ImportError as e:
    logger.critical(f"Failed to import services/dependencies: {e}. Cannot start.")
    raise


# Application lifespan + background tasks live in app_lifespan.py.
from app_lifespan import lifespan  # noqa: E402

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
            except (ValueError, TypeError):
                # Body was not valid JSON; the missing-credentials check below handles it.
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

# --- People lifecycle routers ---
# Registered BEFORE comprehensive_routes on purpose. FastAPI matches routes in
# registration order, and comprehensive_routes owns catch-all path params such as
# /hr/performance/{employee_id} and /hr/comp/{employee_id}. Registered first,
# those swallow the literal sibling paths here: GET /hr/comp/cycles was matched as
# employee_id="cycles" and 500'd, and GET /hr/performance/cycles returned a
# fabricated-looking empty review record for an employee named "cycles".
# The routers below use dedicated prefixes and declare no top-level bare path
# param, so nothing in comprehensive_routes is shadowed by this ordering.
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

# --- Include Service Routers ---
try:
    from services.comprehensive_routes import ALL_ROUTERS
    for router in ALL_ROUTERS:
        api.include_router(router)
except ImportError:
    pass

app.include_router(api, prefix="/api")

# =========================================================================
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

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server in development mode...")
    # Using app:app to support the lifespan management in uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)