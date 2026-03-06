import pytest
from unittest.mock import MagicMock, patch

from app.services.dlq_service import get_dlq_jobs
from app.models.job import Job, JobStatus


@pytest.fixture
def mock_db():
    return MagicMock()


def _make_job(job_id="job-123"):
    job = MagicMock(spec=Job)
    job.id = job_id
    job.status = JobStatus.failed
    return job


def test_get_dlq_jobs_returns_matching_jobs(mock_db):
    job = _make_job("abc-123")
    mock_db.query().filter().first.return_value = job

    with patch("app.services.dlq_service.get_redis") as mock_redis_fn:
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = ["abc-123"]
        mock_redis_fn.return_value = mock_redis

        result = get_dlq_jobs(mock_db)

    assert result == [job]


def test_get_dlq_jobs_empty_queue(mock_db):
    with patch("app.services.dlq_service.get_redis") as mock_redis_fn:
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []
        mock_redis_fn.return_value = mock_redis

        result = get_dlq_jobs(mock_db)

    assert result == []
    mock_db.query.assert_not_called()


def test_get_dlq_jobs_skips_missing_db_rows(mock_db):
    mock_db.query().filter().first.return_value = None

    with patch("app.services.dlq_service.get_redis") as mock_redis_fn:
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = ["ghost-id"]
        mock_redis_fn.return_value = mock_redis

        result = get_dlq_jobs(mock_db)

    assert result == []


def test_get_dlq_jobs_multiple_entries(mock_db):
    jobs = [_make_job(f"job-{i}") for i in range(3)]
    mock_db.query().filter().first.side_effect = jobs

    with patch("app.services.dlq_service.get_redis") as mock_redis_fn:
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [f"job-{i}" for i in range(3)]
        mock_redis_fn.return_value = mock_redis

        result = get_dlq_jobs(mock_db)

    assert len(result) == 3


def test_get_dlq_jobs_reads_full_redis_list(mock_db):
    with patch("app.services.dlq_service.get_redis") as mock_redis_fn:
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []
        mock_redis_fn.return_value = mock_redis

        get_dlq_jobs(mock_db)

    from app.queue.producer import DLQ_NAME
    mock_redis.lrange.assert_called_once_with(DLQ_NAME, 0, -1)
