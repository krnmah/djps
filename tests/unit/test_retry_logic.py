import pytest
from unittest.mock import MagicMock, patch

from app.services.retry_service import handle_job_failure
from app.models.job import JobStatus


def make_job(retry_count=0):
    job = MagicMock()
    job.id = "test-job-uuid"
    job.retry_count = retry_count
    job.status = JobStatus.queued
    return job



# Test 1: First failure — still below max → re-queue
def test_retry_below_max_requeues_job():
    db = MagicMock()
    enqueue_fn = MagicMock()
    job = make_job(retry_count=0)

    with patch("app.services.retry_service.get_settings") as mock_settings, \
         patch("app.services.retry_service.time.sleep") as mock_sleep:
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0
        handle_job_failure(db, job, enqueue_fn)

    assert job.retry_count == 1
    assert job.status == JobStatus.queued
    db.commit.assert_called_once()
    # retry_count=1 → delay = 2^1 = 2.0s
    mock_sleep.assert_called_once_with(2.0)
    enqueue_fn.assert_called_once_with("test-job-uuid")


# Test 2: Second failure — still below max → re-queue again
def test_retry_second_failure_requeues_job():
    db = MagicMock()
    enqueue_fn = MagicMock()
    job = make_job(retry_count=1)

    with patch("app.services.retry_service.get_settings") as mock_settings, \
         patch("app.services.retry_service.time.sleep") as mock_sleep:
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0
        handle_job_failure(db, job, enqueue_fn)

    assert job.retry_count == 2
    assert job.status == JobStatus.queued
    # retry_count=2 → delay = 2^2 = 4.0s
    mock_sleep.assert_called_once_with(4.0)
    enqueue_fn.assert_called_once_with("test-job-uuid")


# Test 3: Final failure — hits max → mark permanently failed
def test_retry_at_max_marks_job_failed():
    db = MagicMock()
    enqueue_fn = MagicMock()
    job = make_job(retry_count=2)

    with patch("app.services.retry_service.get_settings") as mock_settings, \
         patch("app.services.retry_service.time.sleep") as mock_sleep:
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0
        handle_job_failure(db, job, enqueue_fn)

    assert job.retry_count == 3
    assert job.status == JobStatus.failed
    db.commit.assert_called_once()
    # no sleep when permanently failing — no point waiting
    mock_sleep.assert_not_called()
    enqueue_fn.assert_not_called()


# Test 4: max_job_retries=1 means zero retries (fail immediately)
def test_no_retries_when_max_is_one():
    db = MagicMock()
    enqueue_fn = MagicMock()
    job = make_job(retry_count=0)

    with patch("app.services.retry_service.get_settings") as mock_settings, \
         patch("app.services.retry_service.time.sleep") as mock_sleep:
        mock_settings.return_value.max_job_retries = 1
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0
        handle_job_failure(db, job, enqueue_fn)

    assert job.retry_count == 1
    assert job.status == JobStatus.failed
    mock_sleep.assert_not_called()
    enqueue_fn.assert_not_called()
