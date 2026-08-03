import pytest
from fastapi.testclient import TestClient
from server import app
import os
from config.settings import settings

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    # Force test environment variables
    os.environ["ENV"] = "test"
    os.environ["MONGO_DB_NAME"] = "hiro_test_db"
    os.environ["POSTGRES_DB"] = "hiro_test_db"
    settings.ENV = "test"
    yield

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def test_user_token(client):
    # Depending on auth_service test user seed
    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return "MOCK_TOKEN_FOR_TESTS"