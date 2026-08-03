# backend/services/data_migration_agent.py
"""Data Migration Agent: Responsible for large-scale, transformative data migration from legacy systems (via ExternalAPIConnector) to the HiRo UDM (Postgres).
Handles schema transformation, chunking, and idempotent insertion."""
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone 
import uuid 

from config.settings import settings
from services.postgres_client import pg_client
from services.external_api_connector import ExternalAPIConnector 
from services.event_publisher_service import EventPublisherService

logger = logging.getLogger(__name__)

# --- Configuration Constants ---
DEFAULT_CHUNK_SIZE = 5000 
MIGRATION_AGENT_ID = "DataMigrationAgent"

class DataMigrationAgent:
    def __init__(self, api_connector: ExternalAPIConnector, publisher: EventPublisherService):
        self.api_connector = api_connector
        self.publisher = publisher
        if not hasattr(publisher, 'TOPIC_MIGRATION_HEARTBEAT'):
             publisher.TOPIC_MIGRATION_HEARTBEAT = "data.migration.heartbeat"
        if not hasattr(publisher, 'TOPIC_AGENT_TASK_COMPLETE'):
             publisher.TOPIC_AGENT_TASK_COMPLETE = "agent.task.complete"
        if not hasattr(publisher, 'TOPIC_POLICY_VIOLATION'):
             publisher.TOPIC_POLICY_VIOLATION = "policy.violation"
             
        logger.info(f"✓ {MIGRATION_AGENT_ID} Initialized.")

    async def _fetch_legacy_data(self, system_id: str, endpoint: str, last_migrated_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # ... (fetch_legacy_data logic remains unchanged) ...
        """Fetches a chunk of legacy data using the external connector."""
        try:
            params = {"chunk_size": DEFAULT_CHUNK_SIZE, "start_id": last_migrated_id}
            
            data_response = await self.api_connector.fetch_data_from_legacy(
                system_id=system_id,
                endpoint=endpoint,
                params=params
            )
            
            if data_response and isinstance(data_response.get('records'), list):
                logger.info(f"Fetched {len(data_response['records'])} records from {system_id}/{endpoint}.")
                return data_response['records']
            
            return []
        except Exception as e:
            logger.error(f"Error fetching legacy data from {system_id}: {type(e).__name__}: {e}")
            return []

    # --- Synchronous Core Transformation Logic ---
    def _perform_transformation(self, records: List[Dict[str, Any]], transform_map: Dict[str, str]) -> List[Dict[str, Any]]:
        # ... (perform_transformation logic remains unchanged) ...
        """Synchronous part: applies mapping and generates stable IDs."""
        transformed = []
        for record in records:
            t = {}
            for legacy_key, udm_key in transform_map.items():
                t[udm_key] = record.get(legacy_key)
                
            # CRITICAL: Generate stable key (UUID generation is synchronous)
            t['legacy_source_id'] = record.get('unique_legacy_id') or str(uuid.uuid4())
            transformed.append(t)
        return transformed

    async def _transform_and_insert_chunk(self,
                                        records: List[Dict[str, Any]],
                                        target_table: str,
                                        transform_map: Dict[str, str]) -> int:
        """
        Applies schema transformation and performs idempotent bulk insertion into UDM.
        """
        if not records:
            return 0
            
        # 1. Transformation (Run safely in a thread)
        transformed_records = await asyncio.to_thread(self._perform_transformation, records, transform_map)
            
        if not transformed_records:
            return 0
        
        # 2. SQL Construction
        columns = list(transformed_records[0].keys())
        cols_str = ', '.join(columns)
        val_placeholders = ', '.join([f"${i+1}" for i in range(len(columns))])
        update_clauses = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != 'legacy_source_id'])
        if not update_clauses:
            update_clauses = "legacy_source_id = EXCLUDED.legacy_source_id" 
            
        upsert_query = f"""
        INSERT INTO {target_table} ({cols_str})
        VALUES ({val_placeholders})
        ON CONFLICT (legacy_source_id) DO UPDATE SET {update_clauses};
        """
        
        # 3. Transactional Upsert (Batch Insertion)
        inserted_count = 0
        async with pg_client.transaction(requesting_agent_id=MIGRATION_AGENT_ID, purpose="bulk_migration_chunk") as conn:
            for record in transformed_records:
                values = [record.get(col) for col in columns]
                try:
                    await conn.execute(upsert_query, *values)
                    inserted_count += 1
                except Exception as e:
                    record_id = record.get('legacy_source_id', 'UNKNOWN_ID')
                    logger.error(f"Postgres upsert FAILED for record ID: {record_id[:8]} in table {target_table}. Error: {type(e).__name__}. Skipping record.")
                    continue 
                    
        return inserted_count

    async def execute_migration_task(self, task_id: str, project_id: str, task_instructions: Dict[str, Any]) -> Dict[str, Any]:
        # ... (Migration execution loop remains unchanged) ...
        """
        Receives an atomic migration task from the orchestrator and executes it.
        """
        logger.info(f"[{task_id}] Starting migration task for project {project_id}.")
        source_system = task_instructions.get("source_system")
        source_endpoint = task_instructions.get("source_endpoint")
        target_table = task_instructions.get("target_udm_table")
        transform_map = task_instructions.get("transform_map", {})
        
        if not all([source_system, source_endpoint, target_table, transform_map]):
            raise ValueError(f"Missing required migration parameters in instructions.")
            
        migrated_count = 0
        last_id = None
        current_chunk = 0
        
        try:
            while True:
                current_chunk += 1
                
                records_chunk = await self._fetch_legacy_data(source_system, source_endpoint, last_id)
                if not records_chunk:
                    break
                
                last_id = records_chunk[-1].get('unique_legacy_id', last_id)
                
                inserted_count = await self._transform_and_insert_chunk(
                    records_chunk, 
                    target_table, 
                    transform_map
                )
                
                migrated_count += inserted_count
                logger.debug(f"[{task_id}] Chunk {current_chunk}: {inserted_count} records upserted.")
                
                if len(records_chunk) < DEFAULT_CHUNK_SIZE:
                    break
                
                await self.publisher.publish_event(
                    self.publisher.TOPIC_MIGRATION_HEARTBEAT,
                    {"task_id": task_id, "project_id": project_id, "records_processed": migrated_count, "last_id": last_id, "timestamp": datetime.now(timezone.utc).isoformat()},
                    key=project_id
                )
            
            await self.publisher.publish_agent_task(
                task_data={
                    "task_id": task_id,
                    "project_id": project_id,
                    "completed_successfully": True,
                    "migration_count": migrated_count,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                topic=self.publisher.TOPIC_AGENT_TASK_COMPLETE,
                key=project_id
            )
            return {
                "status": "SUCCESS", 
                "message": f"Data migration task completed.\n{migrated_count} records upserted to {target_table}.",
                "records_migrated": migrated_count,
            }
        except Exception as e:
            failure_details = f"Migration failed at chunk {current_chunk}: {type(e).__name__} - {e}"
            logger.error(failure_details)
            
            await self.publisher.publish_agent_task(
                task_data={
                    "task_id": task_id, 
                    "project_id": project_id,
                    "completed_successfully": False,
                    "failure_details": [failure_details],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                topic=self.publisher.TOPIC_POLICY_VIOLATION, 
                key=project_id
            )
            
            raise RuntimeError(f"Migration Task Failed: {failure_details}")
