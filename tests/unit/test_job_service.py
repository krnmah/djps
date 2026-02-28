import pytest
from unittest.mock import MagicMock
from app.services.job_service import create_job
from app.models.job import Job, JobStatus

@pytest.fixture
def mock_db():
    return MagicMock()

def test_create_job_new(mock_db):
    mock_db.query().filter_by().first.return_value = None

    mock_db.add.return_value = None
    mock_db.commit.return_value = None
    mock_db.refresh.side_effect = lambda job: None

    payload = {"task": "unit-test"}
    idempotency_key = "unit-key-1"

    job = create_job(mock_db, payload, idempotency_key)

    assert job.payload == payload
    assert job.status == JobStatus.queued
    assert job.idempotency_key == idempotency_key
    mock_db.add.assert_called_once_with(job)
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(job)

def test_create_job_idempotent(mock_db):
    existing_job = Job(payload={"task": "exists"}, status=JobStatus.queued, idempotency_key="unit-key-2")
    mock_db.query().filter_by().first.return_value = existing_job

    payload = {"task": "should-not-create"}
    idempotency_key = "unit-key-2"

    job = create_job(mock_db, payload, idempotency_key)

    # Should return the existing job, not create a new one
    assert job is existing_job
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.refresh.assert_not_called()