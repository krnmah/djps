import time
import threading
import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.main import app
from app.api.deps import get_db
from app.models.base import Base
from app.models.job import Job, JobStatus

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


# Override DB dependency for the FastAPI client
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_worker_processes_job_to_completion(client):
    from app.workers.worker import process_jobs

    with patch("app.services.job_executor.random.random", return_value=1.0), \
         patch("httpx.Client") as mock_http, \
         patch("app.workers.worker.SessionLocal", TestingSessionLocal), \
         patch("app.queue.redis_client.get_settings") as mock_settings:

        # Point both the API producer and worker consumer to the test Redis
        mock_settings.return_value.redis_url = TEST_REDIS_URL
        mock_http.return_value.__enter__.return_value.get.return_value.raise_for_status.return_value = None

        response = client.post("/jobs", json={"payload": {"task": "worker_test"}})
        assert response.status_code == 201
        job_id = response.json()["id"]

        t = threading.Thread(target=process_jobs, kwargs={"max_iterations": 2}, daemon=True)
        t.start()
        t.join(timeout=12)

        db = TestingSessionLocal()
        job = db.query(Job).filter(Job.id == job_id).first()
        db.close()

        assert job.status == JobStatus.completed


def test_worker_marks_job_failed_on_error(client):
    from app.workers.worker import process_jobs

    with patch("app.services.job_executor.random.random", return_value=0.0), \
         patch("app.workers.worker.SessionLocal", TestingSessionLocal), \
         patch("app.services.retry_service.time.sleep"), \
         patch("app.queue.redis_client.get_settings") as mock_settings:

        mock_settings.return_value.redis_url = TEST_REDIS_URL

        response = client.post("/jobs", json={"payload": {"task": "fail_test"}})
        assert response.status_code == 201
        job_id = response.json()["id"]

        t = threading.Thread(target=process_jobs, kwargs={"max_iterations": 4}, daemon=True)
        t.start()
        t.join(timeout=12)

        db = TestingSessionLocal()
        job = db.query(Job).filter(Job.id == job_id).first()
        db.close()

        assert job.status == JobStatus.failed
        assert job.retry_count == 3   # exhausts all 3 attempts (max_job_retries=3)