from unittest.mock import MagicMock
from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.api.deps import get_db
from app.models.job import Job, JobStatus


# Fixtures
def _make_job(
    job_id=None,
    status=JobStatus.queued,
    retry_count=0,
    idempotency_key=None,
):
    job = MagicMock(spec=Job)
    job.id = job_id or uuid.uuid4()
    job.status = status
    job.payload = {"task": "test"}
    job.retry_count = retry_count
    job.idempotency_key = idempotency_key
    job.job_type = "http_request"
    job.result_json = None
    job.error_code = None
    job.error_message = None
    job.created_at = datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)
    job.updated_at = datetime(2026, 3, 5, 12, 0, 1, tzinfo=timezone.utc)
    job.last_attempt_at = None
    job.completed_at = None
    return job


@pytest.fixture(scope="module")
def client():
    _app = create_app()
    mock_db = MagicMock()
    _app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(_app) as c:
        c._mock_db = mock_db
        yield c
    _app.dependency_overrides.clear()


# GET /jobs/{job_id} — single job
class TestGetJobById:
    def test_returns_200_with_job_fields(self, client):
        job_id = uuid.uuid4()
        job = _make_job(job_id=job_id, status=JobStatus.completed, retry_count=1)
        client._mock_db.query.return_value.filter.return_value.first.return_value = job

        resp = client.get(f"/jobs/{job_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(job_id)
        assert data["status"] == "completed"
        assert data["retry_count"] == 1
        assert data["payload"] == {"task": "test"}

    def test_timestamps_present_in_response(self, client):
        job_id = uuid.uuid4()
        job = _make_job(job_id=job_id)
        client._mock_db.query.return_value.filter.return_value.first.return_value = job

        data = client.get(f"/jobs/{job_id}").json()

        assert "created_at" in data
        assert "updated_at" in data
        assert "last_attempt_at" in data

    def test_returns_404_for_unknown_job(self, client):
        client._mock_db.query.return_value.filter.return_value.first.return_value = None

        resp = client.get(f"/jobs/{uuid.uuid4()}")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Job not found"

    def test_returns_422_for_invalid_uuid(self, client):
        resp = client.get("/jobs/not-a-uuid")
        assert resp.status_code == 422

    @pytest.mark.parametrize("job_status", list(JobStatus))
    def test_all_statuses_returned_correctly(self, client, job_status):
        job_id = uuid.uuid4()
        job = _make_job(job_id=job_id, status=job_status)
        client._mock_db.query.return_value.filter.return_value.first.return_value = job

        data = client.get(f"/jobs/{job_id}").json()
        assert data["status"] == job_status.value


# GET /jobs — list endpoint
class TestListJobs:
    def _setup_list(self, client, items, total=None):
        total = total if total is not None else len(items)
        q = client._mock_db.query.return_value
        q.filter.return_value = q
        q.count.return_value = total
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = items
        return q

    def test_returns_list_with_metadata(self, client):
        jobs = [_make_job() for _ in range(3)]
        self._setup_list(client, jobs)

        resp = client.get("/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert len(data["items"]) == 3

    def test_default_limit_is_20(self, client):
        self._setup_list(client, [])
        data = client.get("/jobs").json()
        assert data["limit"] == 20

    def test_custom_limit_and_offset(self, client):
        jobs = [_make_job() for _ in range(5)]
        self._setup_list(client, jobs, total=50)

        resp = client.get("/jobs?limit=5&offset=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 10
        assert data["total"] == 50

    def test_limit_above_100_is_rejected(self, client):
        resp = client.get("/jobs?limit=101")
        assert resp.status_code == 422

    def test_negative_offset_is_rejected(self, client):
        resp = client.get("/jobs?offset=-1")
        assert resp.status_code == 422

    def test_zero_limit_is_rejected(self, client):
        resp = client.get("/jobs?limit=0")
        assert resp.status_code == 422

    def test_filter_by_valid_status(self, client):
        jobs = [_make_job(status=JobStatus.failed) for _ in range(2)]
        self._setup_list(client, jobs, total=2)

        resp = client.get("/jobs?status=failed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "failed"

    def test_invalid_status_filter_rejected(self, client):
        resp = client.get("/jobs?status=nonsense")
        assert resp.status_code == 422

    def test_empty_list_returned_when_no_jobs(self, client):
        self._setup_list(client, [], total=0)

        data = client.get("/jobs").json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.parametrize("status_val", ["queued", "processing", "completed", "failed"])
    def test_all_status_filter_values_accepted(self, client, status_val):
        self._setup_list(client, [], total=0)
        resp = client.get(f"/jobs?status={status_val}")
        assert resp.status_code == 200
