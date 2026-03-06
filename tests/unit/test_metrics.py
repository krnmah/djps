from unittest.mock import MagicMock, patch


def _counter_value(counter) -> float:
    return counter._value.get()

def _reset_counter(counter):
    counter._value.set(0)


# Test 1: JOBS_CREATED increments on successful POST /jobs
def test_jobs_created_increments():
    from app.metrics.metrics import JOBS_CREATED
    from app.api.routes.jobs import create_job
    from app.schemas.job import JobCreate
    from starlette.requests import Request as StarletteRequest

    _reset_counter(JOBS_CREATED)

    mock_db = MagicMock()
    mock_db.query().filter_by().first.return_value = None
    mock_db.add.return_value = None
    mock_db.commit.return_value = None
    mock_db.refresh.side_effect = lambda j: None

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/jobs",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 8000),
    }
    request = StarletteRequest(scope)

    job_in = JobCreate(payload={"t": "m1"})
    before = _counter_value(JOBS_CREATED)
    with patch("app.services.job_service.enqueue_job"):
        create_job(request=request, job_in=job_in, db=mock_db)
    after = _counter_value(JOBS_CREATED)

    assert after == before + 1

# Test 2: JOBS_RETRIED increments on each retry
def test_jobs_retried_increments():
    from app.metrics.metrics import JOBS_RETRIED
    from app.services.retry_service import handle_job_failure
    from app.models.job import Job, JobStatus

    _reset_counter(JOBS_RETRIED)

    mock_db = MagicMock()
    job = Job(payload={"t": "retry"}, status=JobStatus.processing)
    job.retry_count = 0

    with patch("app.services.retry_service.time.sleep"), \
         patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0

        before = _counter_value(JOBS_RETRIED)
        handle_job_failure(mock_db, job, lambda jid: None, lambda jid: None)
        after = _counter_value(JOBS_RETRIED)

    assert after == before + 1

# Test 3: JOBS_FAILED increments when job is permanently failed
def test_jobs_failed_increments_on_permanent_failure():
    from app.metrics.metrics import JOBS_FAILED
    from app.services.retry_service import handle_job_failure
    from app.models.job import Job, JobStatus

    _reset_counter(JOBS_FAILED)

    mock_db = MagicMock()
    job = Job(payload={"t": "perm_fail"}, status=JobStatus.processing)
    job.retry_count = 2

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0

        before = _counter_value(JOBS_FAILED)
        handle_job_failure(mock_db, job, lambda jid: None, lambda jid: None)
        after = _counter_value(JOBS_FAILED)

    assert after == before + 1

# Test 4: JOBS_RETRIED does NOT increment on permanent failure
def test_jobs_retried_does_not_increment_on_permanent_failure():
    from app.metrics.metrics import JOBS_RETRIED
    from app.services.retry_service import handle_job_failure
    from app.models.job import Job, JobStatus

    _reset_counter(JOBS_RETRIED)

    mock_db = MagicMock()
    job = Job(payload={"t": "pf2"}, status=JobStatus.processing)
    job.retry_count = 2

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0

        before = _counter_value(JOBS_RETRIED)
        handle_job_failure(mock_db, job, lambda jid: None, lambda jid: None)
        after = _counter_value(JOBS_RETRIED)

    assert after == before
