# /backend/services/event_publisher_service.py - MODIFIED FOR NEW TOPIC AND SIGNATURE CONSISTENCY

import logging
import json
import hashlib
import asyncio
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
from config.settings import settings

# --- NATS IMPORTS WITH ROBUST FALLBACK ---
try:
    import nats
    from nats.errors import ConnectionClosedError, TimeoutError, NoServersError
    from nats.js.errors import APIError as NatsAPIError
except ImportError:
    nats = None
    class NatsAPIError(Exception): pass

logger = logging.getLogger(__name__)

# Signing secret for security
AGENT_SIGNING_SECRET = (
    settings.AGENT_SIGNING_SECRET.get_secret_value()
    if hasattr(settings.AGENT_SIGNING_SECRET, "get_secret_value")
    else "default_insecure_secret_for_dev"
)

class EventPublisherService:
    # --- Topic Constants ---
    TOPIC_AGENT_TASK_COMPLETE = "agent.task.complete"
    TOPIC_POLICY_VIOLATION = "policy.violation"
    TOPIC_POLICY_DECISION = "policy.decision"
    TOPIC_COMP_CHANGE = "hr.compensation.change"
    TOPIC_EMPLOYEE_ACTION = "hr.employee.action"
    TOPIC_DTLA_SCENARIO = "dtla.scenario.generated"
    TOPIC_TIMESHEET_TO_AGENT = "hr.timesheet.to_agent"
    TOPIC_AGENT_TASK_ASSIGNED = "agent.task.assigned"
    TOPIC_MIGRATION_HEARTBEAT = "data.migration.heartbeat"
    TOPIC_TELEMETRY = "system.telemetry"
    TOPIC_HUMAN_APPROVAL = "agent.approval.human" 

    def __init__(self, agent_id: str = "OrchestratorKernel"):
        self.nc = None
        self.js = None
        self.agent_id = agent_id
        self.telemetry_subscribers: Set[str] = set()
        self.mock_mode = False
        # The outcome of the most recent publish attempt, so a status endpoint can
        # say whether events are actually reaching the bus. Publish failures used
        # to be logged and nothing else, leaving every caller unable to tell a
        # delivered event from a dropped one.
        self.last_publish: Optional[Dict[str, Any]] = None

    async def connect(self, nats_url: str):
        """
        Connects to NATS and initializes JetStream.
        """
        if nats is None:
            logger.warning("NATS library not installed. Running in MOCK mode.")
            self.mock_mode = True
            return

        try:
            # Connect to NATS server
            self.nc = await nats.connect(
                nats_url,
                connect_timeout=10,
                max_reconnect_attempts=10,
                reconnect_time_wait=2
            )
            
            # Initialize JetStream context
            self.js = self.nc.jetstream()
            logger.info(f"✅ Connected to NATS JetStream at {nats_url}")

            # Initialize streams
            await self._initialize_si_streams()

        except Exception as e:
            logger.error(f"❌ NATS Connection failed: {e}")
            self.mock_mode = True

    async def _initialize_si_streams(self):
        """
        Idempotently creates the required streams.
        """
        if self.mock_mode or not self.js:
            return

        # Define streams to create
        streams_config = [
            {
                "name": "HIRO_EVENTS",
                "subjects": ["agent.*", "policy.*", "hr.*", "dtla.*"],
                "retention": "limits",
                "max_msgs": 10000,
                # FIXED: max_age must be in SECONDS (float), not nanoseconds
                "max_age": 24 * 60 * 60,  # 24 hours in seconds = 86400.0
            },
            {
                "name": "HIRO_TELEMETRY",
                "subjects": ["system.telemetry"],
                "retention": "limits",
                "max_msgs": 1000,
                "max_age": 60 * 60,  # 1 hour in seconds = 3600.0
            }
        ]

        for config in streams_config:
            try:
                await self.js.add_stream(**config)
                logger.info(f"🌊 Stream '{config['name']}' ready.")
            except NatsAPIError as e:
                if e.err_code == 10058:
                    # Config conflict - try to delete and recreate
                    logger.warning(f"Stream '{config['name']}' config conflict, attempting to recreate...")
                    try:
                        await self.js.delete_stream(config['name'])
                        await asyncio.sleep(0.5)  # Brief delay to ensure deletion completes
                        await self.js.add_stream(**config)
                        logger.info(f"🔄 Stream '{config['name']}' recreated successfully.")
                    except Exception as recreate_error:
                        logger.error(f"Failed to recreate stream '{config['name']}': {recreate_error}")
                elif e.err_code == 10065:
                    pass  # Stream already exists with same config
                else:
                    logger.warning(f"Stream '{config['name']}' init warning: {e}")
            except Exception as e:
                logger.error(f"Failed to init stream '{config['name']}': {e}")

    def _record_publish(self, topic: str, delivered: bool, detail: str) -> bool:
        self.last_publish = {
            "topic": topic,
            "delivered": delivered,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        return delivered

    async def publish_event(self, topic: str, payload: Dict[str, Any], key: str = "") -> bool:
        """
        Publishes an event to NATS JetStream.

        Returns True only when the broker acknowledged the message. Callers that
        care about delivery can now check; callers that must not be blocked by a
        dead bus (every DB write path in this app) can keep ignoring it, which is
        the correct behaviour -- a persisted record is not conditional on an
        event reaching a message bus.
        """
        # 1. Sign the payload
        signed_payload = self._sign_payload(payload)

        # 2. Add timestamp if missing
        if "timestamp" not in signed_payload:
            signed_payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        # 3. Serialize
        data_bytes = json.dumps(signed_payload, default=str).encode("utf-8")

        # 4. Publish (Mock or Real)
        if self.mock_mode or not self.js:
            logger.debug(f"[MOCK PUBLISH] Topic: {topic}, Data: {signed_payload.keys()}")
            return self._record_publish(
                topic, False,
                "No message bus is connected, so this event was not delivered anywhere.")

        try:
            ack = await self.js.publish(topic, data_bytes, timeout=5.0)
            logger.debug(f"📤 Published to {topic} (Seq: {ack.seq})")
            return self._record_publish(topic, True, f"Acknowledged by the message bus (seq {ack.seq}).")
        except NatsAPIError as e:
            if e.err_code == 10059:
                logger.error(f"❌ Stream not found for topic {topic}. Check stream config.")
                return self._record_publish(
                    topic, False, f"No stream is configured to receive '{topic}'.")
            logger.error(f"❌ NATS API Error publishing to {topic}: {e}")
            return self._record_publish(topic, False, f"The message bus rejected the event: {e}")
        except Exception as e:
            logger.error(f"❌ General Error publishing to {topic}: {e}")
            return self._record_publish(
                topic, False, f"The event could not be sent: {type(e).__name__}: {e}")

    async def publish_agent_task(self, task_data: Dict[str, Any], topic: str, key: str = "") -> bool:
        """Wrapper for publishing agent tasks"""
        return await self.publish_event(topic, task_data, key)

    async def publish_telemetry_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Specialized publisher for high-frequency telemetry"""
        return await self.publish_event(self.TOPIC_TELEMETRY, metrics)

    def _sign_payload(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [CRITICAL: ZERO TRUST] Adds a cryptographic signature to the payload.
        Ensures metadata is always present for verification.
        """
        if not self.agent_id:
            return event_data

        payload_to_sign = event_data.copy()
        
        # 1. Ensure metadata is present for the signing process
        if "metadata" not in payload_to_sign:
            payload_to_sign["metadata"] = {}
        
        # 2. Add source agent ID before signing
        payload_to_sign["metadata"]["source_agent_id"] = self.agent_id
        
        # 3. Create canonical payload string (sorted keys ensure consistent hash)
        payload_str = json.dumps(payload_to_sign, sort_keys=True, default=str)
        signing_key = f"{AGENT_SIGNING_SECRET}-{self.agent_id}".encode("utf-8")
        
        # 4. Generate the signature
        signature_core = hashlib.sha256(signing_key + payload_str.encode("utf-8")).hexdigest()[:16].upper()
        signature = f"SIG_{self.agent_id}_{signature_core}"
        
        # 5. Attach the signature and return the full payload
        payload_to_sign["metadata"]["signature"] = signature
        
        return payload_to_sign

    def add_telemetry_subscriber(self, subscriber_id: str):
        self.telemetry_subscribers.add(subscriber_id)
        logger.debug(f"Added telemetry subscriber: {subscriber_id}")

    def remove_telemetry_subscriber(self, subscriber_id: str):
        if subscriber_id in self.telemetry_subscribers:
            self.telemetry_subscribers.remove(subscriber_id)
            logger.debug(f"Removed telemetry subscriber: {subscriber_id}")

    async def close(self):
        """Gracefully close NATS connection"""
        if self.nc:
            try:
                await self.nc.close()
                logger.info("NATS connection closed.")
            except Exception as e:
                logger.error(f"Error closing NATS connection: {e}")
