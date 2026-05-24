# /backend/tests/test_upload.py - FIXED
"""Test File Upload and Background Processing"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import io
from pathlib import Path
import os
import csv 
import json 
import tempfile
import shutil
from typing import Dict, Any # CRITICAL FIX: Add missing imports

# Import the service function we are testing
from services.ingestion_agent import process_stream
# CRITICAL FIX: Import the actual processor implementation class/method. 
# The function is synchronous core logic of the processor class. 
# Since process_stream uses asyncio.to_thread with a dynamically created processor instance, 
# patching the internal sync function call within the context manager is easier.
# For mock, we will patch the `asyncio.to_thread` usage in `process_stream`.
from services.event_publisher_service import EventPublisherService 

@pytest.fixture
def mock_publisher():
    publisher = MagicMock(spec=EventPublisherService)
    publisher.publish_event = AsyncMock(return_value=True)
    return publisher

@pytest.mark.asyncio
async def test_streaming_upload_writes_and_cleans_up(tmp_path, mock_publisher):
    """
    Tests that process_stream correctly handles the file, calls the sync processor,
    and ensures cleanup 
    functions are called.
    """
    file_content = b"header,data1,data2\nrecord1,A,1\nrecord2,B,2"
    file_stream = io.BytesIO(file_content)
    file_name = "test_upload.csv"
    user_id = "test_admin"
    
    # Mock the return value of the internal synchronous processing step
    mock_records: List[Dict[str, Any]] = [
        {"ingestion_id": "ID1", "user_id": user_id, "filename": file_name, "data": '{"A": 1}', "vector": "{0.0}", "created_at": datetime.now(timezone.utc).isoformat()},
        {"ingestion_id": "ID2", "user_id": user_id, "filename": file_name, "data": '{"A": 2}', "vector": "{0.0}", "created_at": datetime.now(timezone.utc).isoformat()},
    ]

    # CRITICAL FIX: Mock the internal module-level publisher used by process_stream
    with patch("services.ingestion_agent.publisher", mock_publisher):
        # CRITICAL FIX: Patch the asyncio.to_thread call to mock the result of the sync processor
        with patch("services.ingestion_agent.shutil.rmtree") as mock_rmtree, \
             patch("services.ingestion_agent.tempfile.mkdtemp", return_value=str(tmp_path / "temp_dir")) as mock_mkdtemp, \
             patch("asyncio.to_thread", side_effect=[io.BytesIO(file_content).read, mock_records]) as to_thread_patch, \
             patch("services.ingestion_agent.pg_client.execute", new=AsyncMock(return_value="INSERT 2")):
            
            result = await process_stream(
                stream=file_stream,
                filename=file_name,
                mime="text/csv", # CRITICAL FIX: Pass mime, not file_type
                user_id=user_id
            )
            
            # Assert top-level success
            assert result["status"] == "success"
            assert result["records_processed"] == 2
            
            # CRITICAL FIX: Ensure cleanup functions were called
            mock_rmtree.assert_called_once()
            
            # Assert publisher event was called asynchronously
            mock_publisher.publish_event.assert_called_once()

@pytest.mark.asyncio
async def test_streaming_upload_handles_processor_failure(tmp_path, mock_publisher):
    """
    Tests that process_stream handles processor exceptions and ensures cleanup.
    """
    file_content = b"malformed data"
    file_stream = io.BytesIO(file_content)
    file_name = "malformed.txt"
    
    # Simulate the synchronous processor raising an exception (second call to to_thread)
    def raise_exc(*args, **kwargs):
        raise Exception("Data parsing failed")
    
    # CRITICAL FIX: Mock publisher and cleanup functions
    with patch("services.ingestion_agent.publisher", mock_publisher):
        with patch("services.ingestion_agent.shutil.rmtree") as mock_rmtree, \
             patch("services.ingestion_agent.tempfile.mkdtemp", return_value=str(tmp_path / "temp_dir")) as mock_mkdtemp, \
             patch("asyncio.to_thread", side_effect=[io.BytesIO(file_content).read, raise_exc]) as to_thread_patch:
            
            result = await process_stream(
                stream=file_stream,
                filename=file_name,
                mime="text/plain",
                user_id="fail_user"
            )
            
            assert result["status"] == "error"
            assert "Data parsing failed" in result["message"]
            
            # CRITICAL FIX: Assert cleanup functions were called regardless of failure
            mock_rmtree.assert_called_once()
            
            # Publisher should not be called on failure in this flow
            mock_publisher.publish_event.assert_not_called()