import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.api.deps import get_db
from app.models.base import Base
import os

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb")

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override DB dependency for all tests in this file
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_enqueue(monkeypatch):
    with patch("app.services.job_service.enqueue_job") as mock:
        yield mock


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
    response1 = client.post("/jobs", json=payload)
    response2 = client.post("/jobs", json=payload)
    assert response1.json()["id"] == response2.json()["id"]


def test_get_job_status(client):
    create_response = client.post("/jobs", json={"payload": {"task": "status-check"}})
    job_id = create_response.json()["id"]

    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == job_id
    assert get_response.json()["status"] == "queued"


def test_get_nonexistent_job(client):
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.get(f"/jobs/{fake_id}")
    assert response.status_code == 404
