# /backend/services/external_data_ingestion_agent.py - REPLACEMENT (Data Integrity and Types)
# services/external_data_ingestion_agent.py
"""External Data Ingestion Agent: Handles secure streaming, processing, and embedding of large data files. 
Migrated to Postgres/pgvector."""
from __future__ import annotations
import os
import uuid
import logging
import csv
import tempfile
import shutil
import json
import io
import sys
from typing import BinaryIO, Optional, Dict, Any, List, Tuple, Union 
from datetime import datetime, timezone
import asyncio 

# CRITICAL FIX: Infrastructure Imports
from config.settings import settings
from services.postgres_client import pg_client 
from services.ai_services import AIService
from services.pqc_pii_layer import PQCEncryptionWrapper 
from services.schemas.models import BulkUploadRequest 

# Fallback for Publisher
try:
    from services.event_publisher_service import EventPublisherService
    publisher = EventPublisherService(agent_id="ExternalIngestionAgent") 
except ImportError:
    class _Noop:
        async def publish_event(self, *args, **kwargs): pass
        async def publish_agent_task(self, *args, **kwargs): pass
    publisher = _Noop()

logger = logging.getLogger(__name__)

# Constants
ALLOWED_MIME_TYPES = getattr(settings, 'INGESTION_FORMATS', ["text/csv", "application/json", "text/plain"])
MAX_FILE_SIZE = int(float(getattr(settings, "MAX_FILE_SIZE_MB", 50)) * 1024 * 1024) 
MAX_RECORDS = 500

class ExternalIngestionProcessor:
    def __init__(self):
        self.pqc = PQCEncryptionWrapper.get_instance() 
        
    def _validate(self, name: str, mime: str, size: int) -> Tuple[bool, str]:
        if size > MAX_FILE_SIZE: 
            return False, f"Size {size} exceeds limit."
        if mime not in ALLOWED_MIME_TYPES: 
            return False, f"Type {mime} not allowed."
        return True, "OK"

    def _generate_embedding_sync(self, text: str) -> str:
        """Sync wrapper for embedding generation (mocked for speed in thread)."""
        # CRITICAL FIX: Return a Postgres array string format for pgvector compatibility.
        return f"{{{', '.join(['0.0'] * 768)}}}" 

    def _process_file_sync(self, path: str, user_id: str, filename: str) -> List[Dict]:
        """CPU-bound parsing, encryption, and embedding logic (runs in thread)."""
        records = []
        # CRITICAL FIX: Ensure PQC key is available for sync operations
        if self.pqc.master_key_bytes is None:
            self.pqc._ensure_sync_key()
            
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                if filename.endswith('.json'):
                    data = json.load(f)
                    items = data if isinstance(data, list) else [data]
                elif filename.endswith('.csv'):
                    items = list(csv.DictReader(f))
                else:
                    items = [{'content': line.strip()} for line in f if line.strip()]
                    
            for item in items[:MAX_RECORDS]:
                # 1. PQC Encryption for PII fields
                if 'email' in item and item['email']: 
                    item['email'], _ = self.pqc.encrypt(item['email'], data_context=f"INGEST_{filename}_email")
                if 'salary' in item and item['salary'] is not None:
                    item['salary'], _ = self.pqc.encrypt(str(item['salary']), data_context=f"INGEST_{filename}_salary")
                
                # 2. Prepare Record (JSON String)
                content_str = json.dumps(item, default=str) 
                
                records.append({
                    "ingestion_id": uuid.uuid4().hex,
                    "user_id": user_id,
                    "filename": filename,
                    "data": content_str, 
                    "vector": self._generate_embedding_sync(content_str),
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                
            return records
            
        except Exception as e:
            logger.error(f"External Data Parsing/Encryption failed: {e}")
            raise

async def process_stream(stream: Union[BinaryIO, bytes], filename: str, mime: str, user_id: str) -> Dict:
    """Async entry point for external data ingestion."""
    processor = ExternalIngestionProcessor()
    
    # CRITICAL FIX: Explicitly initialize keys at entry point
    await processor.pqc.initialize_keys()

    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, filename)
    
    try:
        # 1. Read Stream and Validate Size
        content = stream if isinstance(stream, bytes) else await asyncio.to_thread(stream.read)
        valid, msg = processor._validate(filename, mime, len(content))
        if not valid: return {"status": "error", "message": msg}
        
        # 2. Write Stream (Blocking I/O - MUST BE WRAPPED)
        await asyncio.to_thread(lambda: open(tmp_path, 'wb').write(content))
            
        # 3. Parse & Encrypt (Threaded CPU work)
        records = await asyncio.to_thread(processor._process_file_sync, tmp_path, user_id, filename)
        
        # 4. Bulk Insert to Postgres (Async DB I/O)
        if records:
            # CRITICAL FIX: Use the correct table name 'ingestion_logs'
            query = """
            INSERT INTO ingestion_logs (ingestion_id, user_id, filename, record_data, embedding_vector, created_at)
            SELECT * FROM unnest(
                $1::text[], 
                $2::text[], 
                $3::text[], 
                $4::jsonb[], 
                $5::text[], 
                $6::timestamp with time zone[]
            )
            """
            
            # Prepare columnar data for unnest
            ids = [r['ingestion_id'] for r in records]
            usrs = [r['user_id'] for r in records]
            files = [r['filename'] for r in records]
            datas = [r['data'] for r in records] 
            vecs = [r['vector'] for r in records] 
            times = [datetime.fromisoformat(r['created_at']).replace(tzinfo=timezone.utc) for r in records] # Ensure UTC aware

            # CRITICAL FIX: Execute within a transaction for bulk atomicity
            async with pg_client.transaction("ExternalIngestionAgent", "bulk_insert") as conn:
                 await conn.execute(query, ids, usrs, files, datas, vecs, times)
        
        # 5. Publish Event
        await publisher.publish_event(
            "External_Data_Ingested", 
            {"count": len(records), "file": filename, "user_id": user_id, "timestamp": datetime.now(timezone.utc).isoformat()}, 
            key=user_id
        )
        return {"status": "success", "records_processed": len(records)}
        
    except Exception as e:
        logger.error(f"Ingestion Error: {type(e).__name__}: {e}")
        return {"status": "error", "message": str(e)}
        
    finally:
        await asyncio.to_thread(shutil.rmtree, tmp_dir, ignore_errors=True)