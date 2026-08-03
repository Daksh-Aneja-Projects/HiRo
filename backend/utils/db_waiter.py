#!/usr/bin/env python3
import os
import sys
import time
import socket
import logging
from urllib.parse import urlparse
import asyncio
from typing import Optional, Dict, Any, List

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None
try:
    import redis
except ImportError:
    redis = None
try:
    import psycopg2
except ImportError:
    psycopg2 = None
try:
    import httpx
except ImportError:
    httpx = None

# --- ADDED: import nats for the functional test (optional if not installed) ---
try:
    import nats
    # Import specific NATS errors for robust connection handling
    from nats.errors import TimeoutError as NatsTimeoutError
    from nats.js.api import StreamConfig, RetentionPolicy
    # JetStream API errors
    try:
        from nats.js.errors import APIError as JetStreamAPIError
    except Exception:
        JetStreamAPIError = None
except ImportError:
    nats = None
    StreamConfig = None
    RetentionPolicy = None
    # Define a placeholder class for error handling if nats is missing
    class NatsTimeoutError(Exception): pass
    JetStreamAPIError = None

logger = logging.getLogger("db_waiter")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

TIMEOUT = int(os.environ.get("DB_WAIT_TIMEOUT", "90"))
INTERVAL = float(os.environ.get("DB_WAIT_INTERVAL", "2.0"))

NATS_CONNECT_TIMEOUT = float(os.environ.get("NATS_CONNECT_TIMEOUT_SECONDS", "5.0"))
NATS_PUBLISH_TIMEOUT = float(os.environ.get("NATS_PUBLISH_TIMEOUT_SECONDS", "5.0"))

def wait_tcp(host: str, port: int, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except Exception:
            time.sleep(min(INTERVAL, 1.0))
    return False

def check_mongo(dsn: str) -> bool:
    if not dsn:
        return False
    if MongoClient is None:
        logger.debug("Dependency missing: pymongo.")
        return False
    try:
        client = MongoClient(dsn, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception as e:
        logger.debug("Mongo check failed: %s", e)
        return False

def check_redis(dsn: str) -> bool:
    if not dsn:
        return False
    if redis is None:
        logger.debug("Dependency missing: redis library.")
        return False
    try:
        r = redis.from_url(dsn, socket_connect_timeout=2)
        r.ping()
        return True
    except Exception as e:
        logger.debug("Redis check failed: %s", e)
        return False

def check_postgres(dsn: str) -> bool:
    if not dsn:
        return False
    if psycopg2:
        try:
            conn = psycopg2.connect(dsn, connect_timeout=2)
            conn.close()
            return True
        except Exception as e:
            logger.debug("Postgres check failed (psycopg2): %s", e)
            pass
    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 5432)
        return wait_tcp(host, port, timeout=2)
    except Exception as e:
        logger.debug("Postgres check fallback failed: %s", e)
        return False

def check_nats(dsn: str) -> bool:
    if not dsn:
        return False
    try:
        parsed = urlparse(dsn)
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 4222)
        return wait_tcp(host, port, timeout=2)
    except Exception as e:
        logger.debug("NATS check failed: %s", e)
        return False

def check_dgraph(dgraph_url: str) -> bool:
    if not dgraph_url:
        return False
    if httpx:
        try:
            with httpx.Client(timeout=3.0) as client:
                response = client.get(f"{dgraph_url}/health")
                if response.status_code == 200:
                    return True
        except Exception as e:
            logger.debug("Dgraph HTTP health check failed: %s", e)
            pass
    try:
        parsed = urlparse(dgraph_url)
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 8080)
        return wait_tcp(host, port, timeout=2)
    except Exception as e:
        logger.debug("Dgraph TCP check failed: %s", e)
        return False

def main() -> int:
    start = time.time()
    mongo_dsn = os.environ.get("MONGO_URL", "mongodb://admin:mongo_secret@mongo:27017")
    redis_dsn = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    postgres_dsn = os.environ.get("POSTGRES_URL", "postgresql://hiro_user:hiro_password@postgres_db:5432/hiro_db")
    nats_dsn = os.environ.get("NATS_URL", "nats://nats:4222")
    dgraph_url = os.environ.get("DGRAPH_URL", "http://dgraph-alpha:8080")

    ok: Dict[str, bool] = {
        "mongo": False,
        "redis": False,
        "postgres": False,
        "nats": False,
        "dgraph": False
    }
    deadline = start + TIMEOUT
    logger.info("Waiting for services (timeout=%ss)...", TIMEOUT)
    logger.info("Services to check: %s", ", ".join(k.upper() for k in ok.keys())) # IMPROVED: Clearer list

    while time.time() < deadline:
        if not ok["mongo"]:
            ok["mongo"] = check_mongo(mongo_dsn)
            if ok["mongo"]:
                logger.info("✅ MongoDB ready")

        if not ok["redis"]:
            ok["redis"] = check_redis(redis_dsn)
            if ok["redis"]:
                logger.info("✅ Redis ready")

        if not ok["postgres"]:
            ok["postgres"] = check_postgres(postgres_dsn)
            if ok["postgres"]:
                logger.info("✅ Postgres ready")

        if not ok["nats"]:
            ok["nats"] = check_nats(nats_dsn)
            if ok["nats"]:
                logger.info("✅ NATS ready")

        if not ok["dgraph"]:
            ok["dgraph"] = check_dgraph(dgraph_url)
            if ok["dgraph"]:
                logger.info("✅ Dgraph ready")

        if all(ok.values()):
            logger.info("✅ All services are ready: %s", ok)

            # -------------------------
            # Functional NATS test (ADDED)
            # -------------------------
            if nats is not None and StreamConfig is not None:
                time.sleep(1.0) 
                
                try:
                    logger.info("🔧 Performing functional NATS test: connect -> ensure stream -> publish -> ack...")
                    
                    async def _nats_test():
                        # Create proper StreamConfig object with retention policy
                        stream_config = StreamConfig(
                            name="HIRO_TEST",
                            subjects=["hiro.test.startup"],
                            retention=RetentionPolicy.LIMITS,
                            max_msgs=10000,
                        )
                        
                        # to fix the "unexpected keyword" error caused by nats-py version differences.
                        nc = await nats.connect(
                            nats_dsn, 
                            connect_timeout=NATS_CONNECT_TIMEOUT, 
                        )
                        js = nc.jetstream()
                        
                        # Auto-create the test stream in an idempotent way
                        try:
                            # Try to get existing stream first (idempotent approach)
                            try:
                                await js.stream_info("HIRO_TEST")
                                logger.info("🛠 JetStream test stream HIRO_TEST already exists")
                            except:
                                # Stream doesn't exist, create it
                                await js.add_stream(stream_config)
                                logger.info("🛠 Created JetStream test stream HIRO_TEST")
                        except Exception as se:
                            # If JetStream isn't available or creation fails, raise to be handled below
                            logger.error(f"JetStream stream creation failed: {se}")
                            await nc.close()
                            raise

                        test_subject = "hiro.test.startup"
                        
                        # Try publishing with a small retry to handle transient conditions
                        publish_attempts = 2
                        last_exc = None
                        for attempt in range(1, publish_attempts + 1):
                            try:
                                ack = await js.publish(
                                    test_subject, 
                                    b"startup-test", 
                                    timeout=NATS_PUBLISH_TIMEOUT 
                                )
                                logger.info(f"🟢 NATS functional publish ACK received (Subject: {test_subject}, Sequence: {getattr(ack, 'seq', ack)})")
                                last_exc = None
                                break
                            except Exception as pe:
                                last_exc = pe
                                logger.warning(f"NATS publish attempt {attempt} failed: {pe}")
                                if attempt < publish_attempts:
                                    await asyncio.sleep(0.5)

                        await nc.close()
                        
                        if last_exc:
                            # Re-raise the last publish exception so outer handler can catch and log
                            raise last_exc

                    asyncio.run(_nats_test())
                    logger.info("🟢 Functional NATS test passed permanently.")
                
                except NatsTimeoutError:
                    # Catch the specific NATS timeout error (or no response from stream)
                    logger.error("❌ Functional NATS test failed: NATS client timed out waiting for JetStream ACK. (Check NATS server -js flag)")
                    return 3
                except Exception as e:
                    logger.error(f"❌ Functional NATS test failed (General error): {e}")
                    return 3
            else:
                logger.warning("⚠️ NATS python client not installed; functional NATS test skipped (TCP test already ran).")
            # -------------------------

            return 0

        ready_count = sum(1 for v in ok.values() if v)
        logger.info("⏳ Services ready: %d/%d", ready_count, len(ok))
        time.sleep(INTERVAL)

    logger.error("❌ Timeout reached. Services status: %s", ok)
    return 2

async def ensure_all_dbs_ready():
    logger.info("Starting async DB readiness check...")
    result_code = await asyncio.to_thread(main)
    if result_code != 0:
        logger.error("❌ Database readiness check failed.")
        raise ConnectionRefusedError("One or more required services failed to become ready.")
    logger.info("✅ Async DB readiness check passed.")

if __name__ == "__main__":
    rc = main()
    sys.exit(rc)

