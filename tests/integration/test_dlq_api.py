import os

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.main import app
from app.api.deps import get_db
from app.models.base import Base
from app.models.job import Job, JobStatus
from app.queue.producer import DLQ_NAME

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")

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

@pytest.fixture
def test_redis():
    r = redis_lib.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    r.delete(DLQ_NAME)
    yield r
    r.delete(DLQ_NAME)

# Test 1: Empty DLQ returns empty list
def test_dlq_empty_returns_empty_list(client, test_redis):
    with patch("app.api.routes.dlq.get_redis", return_value=test_redis):
        response = client.get("/dlq")

    assert response.status_code == 200
    assert response.json() == []

# Test 2: DLQ returns the failed job with full details
def test_dlq_returns_failed_job(client, test_redis):
    db = TestingSessionLocal()
    job = Job(payload={"task": "dlq-test"}, status=JobStatus.failed, retry_count=3)
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = str(job.id)
    db.close()

    test_redis.rpush(DLQ_NAME, job_id)

    with patch("app.api.routes.dlq.get_redis", return_value=test_redis):
        response = client.get("/dlq")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == job_id
    assert data[0]["status"] == "failed"
    assert data[0]["retry_count"] == 3

# Test 3: Multiple jobs returned in insertion order
def test_dlq_returns_multiple_jobs_in_order(client, test_redis):
    db = TestingSessionLocal()
    job1 = Job(payload={"n": 1}, status=JobStatus.failed, retry_count=3)
    job2 = Job(payload={"n": 2}, status=JobStatus.failed, retry_count=3)
    db.add_all([job1, job2])
    db.commit()
    db.refresh(job1)
    db.refresh(job2)
    id1, id2 = str(job1.id), str(job2.id)
    db.close()

    # rpush adds to the tail: id1 first, id2 second
    test_redis.rpush(DLQ_NAME, id1)
    test_redis.rpush(DLQ_NAME, id2)

    with patch("app.api.routes.dlq.get_redis", return_value=test_redis):
        response = client.get("/dlq")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == id1
    assert data[1]["id"] == id2

# Test 4: Ghost IDs in DLQ (job deleted from DB) are silently skipped
def test_dlq_skips_job_ids_not_in_db(client, test_redis):
    import uuid
    ghost_id = str(uuid.uuid4())
    test_redis.rpush(DLQ_NAME, ghost_id)

    with patch("app.api.routes.dlq.get_redis", return_value=test_redis):
        response = client.get("/dlq")

    assert response.status_code == 200
    assert response.json() == []
