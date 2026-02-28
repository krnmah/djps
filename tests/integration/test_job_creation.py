import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.models.base import Base
import os

DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb")

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    # create tables
    Base.metadata.create_all(bind=engine)
    yield
    # drops tables after tests
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

def test_create_job(client):
    payload = {
        "payload": {"task": "test"},
        "idempotency_key": "unique-key-1"
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["payload"] == {"task": "test"}
    assert data["idempotency_key"] == "unique-key-1"
    assert data["status"] == "queued"
    assert "id" in data

def test_idempotency(client):
    payload = {
        "payload": {"task": "test"},
        "idempotency_key": "unique-key-2"
    }
    # First request
    response1 = client.post("/jobs", json=payload)
    # Second request with same idempotency_key
    response2 = client.post("/jobs", json=payload)
    assert response1.json()["id"] == response2.json()["id"]