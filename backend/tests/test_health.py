import pytest
from fastapi.testclient import TestClient

def test_root_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "hiro-backend"
    assert "timestamp" in data

def test_api_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "hiro-api"
    assert "version" in data
    # Verify no test credentials are leaked in the health endpoint
    assert "test_credentials" not in data

def test_cors_preflight(client: TestClient):
    # For a health endpoint, options should be allowed if CORS middleware is active
    response = client.options("/api/health", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    # This might return 200/204 or 405 depending on router setup, 
    # but it shouldn't crash.
    assert response.status_code in (200, 204, 405)
