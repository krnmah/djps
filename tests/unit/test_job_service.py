import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError

from app.services.job_service import (
    create_job,
    get_job_by_id,
    list_jobs,
    DuplicateIdempotencyKeyError,
)
from app.schemas.job import JobListResponse
from app.models.job import Job, JobStatus


@pytest.fixture
def mock_db():
    return MagicMock()


# create_job
def test_create_job_new(mock_db):
    mock_db.query().filter_by().first.return_value = None
    mock_db.add.return_value = None
    mock_db.commit.return_value = None
    mock_db.refresh.side_effect = lambda job: None

    payload = {"task": "unit-test"}
    idempotency_key = "unit-key-1"

    with patch("app.services.job_service.enqueue_job"):
        job = create_job(mock_db, payload, idempotency_key)

    assert job.payload == payload
    assert job.status == JobStatus.queued
    assert job.idempotency_key == idempotency_key
    mock_db.add.assert_called_once_with(job)
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(job)


def test_create_job_idempotent(mock_db):
    existing_job = Job(
        payload={"task": "exists"}, status=JobStatus.queued, idempotency_key="unit-key-2"
    )
    mock_db.query().filter_by().first.return_value = existing_job

    with patch("app.services.job_service.enqueue_job") as mock_enqueue:
        job = create_job(mock_db, {"task": "should-not-create"}, "unit-key-2")

    assert job is existing_job
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.refresh.assert_not_called()
    mock_enqueue.assert_not_called()


def test_create_job_enqueues_after_insert(mock_db):
    mock_db.query().filter_by().first.return_value = None
    mock_db.refresh.side_effect = lambda job: None

    with patch("app.services.job_service.enqueue_job") as mock_enqueue:
        job = create_job(mock_db, {"task": "enqueue-test"}, None)

    mock_enqueue.assert_called_once_with(str(job.id))


def test_create_job_increments_jobs_created_counter(mock_db):
    mock_db.query().filter_by().first.return_value = None
    mock_db.refresh.side_effect = lambda job: None

    with (
        patch("app.services.job_service.enqueue_job"),
        patch("app.services.job_service.JOBS_CREATED") as mock_counter,
    ):
        create_job(mock_db, {"task": "counter-test"}, None)

    mock_counter.inc.assert_called_once()


def test_create_job_race_condition_returns_existing(mock_db):
    """IntegrityError followed by a successful lookup returns the existing job."""
    existing = Job(
        payload={"task": "race"}, status=JobStatus.queued, idempotency_key="race-key"
    )
    mock_db.commit.side_effect = IntegrityError(None, None, None)
    mock_db.query().filter_by().first.side_effect = [None, existing]

    with patch("app.services.job_service.enqueue_job") as mock_enqueue:
        job = create_job(mock_db, {"task": "race"}, "race-key")

    assert job is existing
    mock_enqueue.assert_not_called()


def test_create_job_race_condition_with_no_recovery_raises(mock_db):
    mock_db.commit.side_effect = IntegrityError(None, None, None)
    mock_db.query().filter_by().first.side_effect = [None, None]

    with (
        patch("app.services.job_service.enqueue_job"),
        pytest.raises(DuplicateIdempotencyKeyError),
    ):
        create_job(mock_db, {"task": "race"}, "bad-key")


# get_job_by_id
def test_get_job_by_id_returns_job(mock_db):
    import uuid
    job_id = uuid.uuid4()
    mock_job = MagicMock(spec=Job)
    mock_db.query().filter().first.return_value = mock_job

    result = get_job_by_id(mock_db, job_id)

    assert result is mock_job


def test_get_job_by_id_returns_none_when_missing(mock_db):
    import uuid
    mock_db.query().filter().first.return_value = None

    result = get_job_by_id(mock_db, uuid.uuid4())

    assert result is None


# list_jobs
def _setup_list_mock(mock_db, items, total):
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.count.return_value = total
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.all.return_value = items
    return q


def test_list_jobs_returns_job_list_response(mock_db):
    import uuid as uuid_mod
    from datetime import datetime, timezone

    def _make_job(i):
        job = MagicMock(spec=Job)
        job.id = uuid_mod.uuid4()
        job.job_type = "http_request"
        job.status = "queued"
        job.payload = {"n": i}
        job.retry_count = 0
        job.idempotency_key = f"key-{i}"
        job.result_json = None
        job.error_code = None
        job.error_message = None
        job.created_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        job.last_attempt_at = None
        job.completed_at = None
        return job

    jobs = [_make_job(i) for i in range(3)]
    _setup_list_mock(mock_db, jobs, total=3)

    result = list_jobs(mock_db)

    assert isinstance(result, JobListResponse)
    assert result.total == 3
    assert len(result.items) == 3
    assert result.limit == 20
    assert result.offset == 0


def test_list_jobs_applies_status_filter(mock_db):
    q = _setup_list_mock(mock_db, [], total=0)

    list_jobs(mock_db, status=JobStatus.failed)

    q.filter.assert_called_once()


def test_list_jobs_no_filter_skips_filter_call(mock_db):
    q = _setup_list_mock(mock_db, [], total=0)

    list_jobs(mock_db, status=None)

    q.filter.assert_not_called()


def test_list_jobs_respects_limit_and_offset(mock_db):
    q = _setup_list_mock(mock_db, [], total=0)

    result = list_jobs(mock_db, limit=5, offset=10)

    q.offset.assert_called_once_with(10)
    q.limit.assert_called_once_with(5)
    assert result.limit == 5
    assert result.offset == 10
