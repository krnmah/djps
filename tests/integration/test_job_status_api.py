import os
import uuid
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.api.deps import get_db
from app.models.base import Base
from app.models.job import Job, JobStatus

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb",
)

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
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_jobs():
    """Wipe the jobs table before every test for isolation."""
    db = TestingSessionLocal()
    db.query(Job).delete()
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    with patch("app.services.job_service.enqueue_job"):
        return TestClient(app)


# helper to insert a job directly
def _insert_job(status=JobStatus.queued, idempotency_key=None, payload=None):
    db = TestingSessionLocal()
    job = Job(
        payload=payload or {"task": "integration-test"},
        status=status,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    db.close()
    return job


# GET /jobs/{job_id}
class TestGetJobByIdIntegration:
    def test_get_existing_job_returns_correct_fields(self, client):
        job = _insert_job(status=JobStatus.queued)
        resp = client.get(f"/jobs/{job.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(job.id)
        assert data["status"] == "queued"
        assert data["retry_count"] == 0
        assert data["payload"] == {"task": "integration-test"}
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_get_completed_job(self, client):
        job = _insert_job(status=JobStatus.completed)
        data = client.get(f"/jobs/{job.id}").json()
        assert data["status"] == "completed"

    def test_get_failed_job(self, client):
        job = _insert_job(status=JobStatus.failed)
        data = client.get(f"/jobs/{job.id}").json()
        assert data["status"] == "failed"

    def test_unknown_id_returns_404(self, client):
        resp = client.get(f"/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_invalid_uuid_returns_422(self, client):
        resp = client.get("/jobs/not-a-real-id")
        assert resp.status_code == 422


# GET /jobs — list endpoint
class TestListJobsIntegration:
    def test_empty_db_returns_empty_list(self, client):
        data = client.get("/jobs").json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_returns_all_inserted_jobs(self, client):
        _insert_job(status=JobStatus.queued)
        _insert_job(status=JobStatus.completed)
        _insert_job(status=JobStatus.failed)

        data = client.get("/jobs").json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_filter_by_status_queued(self, client):
        _insert_job(status=JobStatus.queued)
        _insert_job(status=JobStatus.queued)
        _insert_job(status=JobStatus.completed)

        data = client.get("/jobs?status=queued").json()
        assert data["total"] == 2
        assert all(item["status"] == "queued" for item in data["items"])

    def test_filter_by_status_completed(self, client):
        _insert_job(status=JobStatus.completed)
        _insert_job(status=JobStatus.failed)

        data = client.get("/jobs?status=completed").json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "completed"

    def test_filter_by_status_failed(self, client):
        _insert_job(status=JobStatus.failed)
        _insert_job(status=JobStatus.queued)

        data = client.get("/jobs?status=failed").json()
        assert data["total"] == 1

    def test_filter_returns_empty_when_none_match(self, client):
        _insert_job(status=JobStatus.queued)

        data = client.get("/jobs?status=failed").json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_pagination_limit(self, client):
        for _ in range(5):
            _insert_job()

        data = client.get("/jobs?limit=3").json()
        assert len(data["items"]) == 3
        assert data["total"] == 5
        assert data["limit"] == 3

    def test_pagination_offset(self, client):
        for _ in range(5):
            _insert_job()

        page1 = client.get("/jobs?limit=3&offset=0").json()
        page2 = client.get("/jobs?limit=3&offset=3").json()

        ids_page1 = {item["id"] for item in page1["items"]}
        ids_page2 = {item["id"] for item in page2["items"]}

        # Pages must not overlap
        assert ids_page1.isdisjoint(ids_page2)
        assert len(page2["items"]) == 2

    def test_offset_beyond_total_returns_empty(self, client):
        _insert_job()

        data = client.get("/jobs?limit=10&offset=100").json()
        assert data["items"] == []
        assert data["total"] == 1

    def test_response_includes_pagination_metadata(self, client):
        _insert_job()

        data = client.get("/jobs?limit=5&offset=0").json()
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "items" in data

    def test_items_include_timestamps(self, client):
        _insert_job()

        data = client.get("/jobs").json()
        item = data["items"][0]
        assert item["created_at"] is not None
        assert item["updated_at"] is not None

    def test_invalid_status_returns_422(self, client):
        resp = client.get("/jobs?status=bogus")
        assert resp.status_code == 422

    def test_limit_over_100_returns_422(self, client):
        resp = client.get("/jobs?limit=999")
        assert resp.status_code == 422

    def test_negative_offset_returns_422(self, client):
        resp = client.get("/jobs?offset=-5")
        assert resp.status_code == 422
