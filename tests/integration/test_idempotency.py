import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from unittest.mock import patch, MagicMock

from app.main import app
from app.api.deps import get_db
from app.models.base import Base
from app.models.job import Job, JobStatus

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb")

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def mock_enqueue():
    with patch("app.api.routes.jobs.enqueue_job") as mock:
        yield mock


# Test 1: Same key sequential — returns same job ID
def test_same_key_returns_same_job(client):
    key = f"idem-{uuid.uuid4()}"
    r1 = client.post("/jobs", json={"payload": {"x": 1}, "idempotency_key": key})
    r2 = client.post("/jobs", json={"payload": {"x": 1}, "idempotency_key": key})

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

# Test 2: Same key, different payload — original job is returned unchanged
def test_same_key_different_payload_returns_original(client):
    key = f"idem-{uuid.uuid4()}"
    r1 = client.post("/jobs", json={"payload": {"version": "first"}, "idempotency_key": key})
    r2 = client.post("/jobs", json={"payload": {"version": "second"}, "idempotency_key": key})

    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["payload"] == {"version": "first"}

# Test 3: No idempotency key — each request creates an independent job
def test_no_key_creates_independent_jobs(client):
    r1 = client.post("/jobs", json={"payload": {"task": "a"}})
    r2 = client.post("/jobs", json={"payload": {"task": "a"}})

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]

# Test 4: enqueue_job called once, NOT on duplicate
def test_enqueue_called_only_once_per_unique_key(client, mock_enqueue):
    key = f"idem-{uuid.uuid4()}"
    client.post("/jobs", json={"payload": {"task": "enq"}, "idempotency_key": key})
    client.post("/jobs", json={"payload": {"task": "enq"}, "idempotency_key": key})

    assert mock_enqueue.call_count == 1

# Test 5: Race condition — DB-level IntegrityError handled gracefully
def test_integrity_error_on_race_condition_returns_existing_job(client):
    key = f"race-{uuid.uuid4()}"

    # pre-insert the winner
    db = TestingSessionLocal()
    winner = Job(payload={"task": "race-winner"}, status=JobStatus.queued, idempotency_key=key)
    db.add(winner)
    db.commit()
    db.refresh(winner)
    winner_id = str(winner.id)
    db.close()

    # custom get_db that makes the initial existence check miss
    first_check_done = {"v": False}

    def patched_get_db():
        db = TestingSessionLocal()
        real_query = db.query

        def query_interceptor(model):
            q = real_query(model)
            if model is Job and not first_check_done["v"]:
                first_check_done["v"] = True
                real_filter_by = q.filter_by

                def filter_by_returning_none(**kwargs):
                    if "idempotency_key" in kwargs:
                        mock = MagicMock()
                        mock.first.return_value = None
                        return mock
                    return real_filter_by(**kwargs)

                q.filter_by = filter_by_returning_none
            return q

        db.query = query_interceptor
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = patched_get_db
    try:
        response = client.post(
            "/jobs",
            json={"payload": {"task": "race-loser"}, "idempotency_key": key},
        )
    finally:
        app.dependency_overrides[get_db] = override_get_db

    # Must return 201 with the winner's job, not 500
    assert response.status_code == 201
    assert response.json()["id"] == winner_id

# Test 6: Unique keys create independent jobs (not deduplicated)
def test_different_keys_create_different_jobs(client):
    """
    Two requests with different idempotency keys must produce two distinct jobs.
    """
    r1 = client.post("/jobs", json={"payload": {"n": 1}, "idempotency_key": f"key-{uuid.uuid4()}"})
    r2 = client.post("/jobs", json={"payload": {"n": 2}, "idempotency_key": f"key-{uuid.uuid4()}"})

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]
