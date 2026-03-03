from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.workers.recovery import requeue_stuck_jobs
from app.models.job import JobStatus

def make_stuck_job(job_id: str, minutes_ago: int = 5):
    job = MagicMock()
    job.id = job_id
    job.status = JobStatus.processing
    job.last_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return job


# Test 1: stuck job is reset to queued and re-enqueued
def test_stuck_job_is_requeued():
    stuck = make_stuck_job("job-stuck-1", minutes_ago=5)

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [stuck]
    enqueue_fn = MagicMock()

    result = requeue_stuck_jobs(db, enqueue_fn, threshold_seconds=60)

    assert stuck.status == JobStatus.queued
    db.commit.assert_called_once()
    enqueue_fn.assert_called_once_with("job-stuck-1")
    assert result == ["job-stuck-1"]

# Test 2: no stuck jobs — nothing happens
def test_no_stuck_jobs_does_nothing():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    enqueue_fn = MagicMock()

    result = requeue_stuck_jobs(db, enqueue_fn, threshold_seconds=60)

    db.commit.assert_not_called()
    enqueue_fn.assert_not_called()
    assert result == []

# Test 3: multiple stuck jobs all get re-queued
def test_multiple_stuck_jobs_all_requeued():
    stuck1 = make_stuck_job("job-a", minutes_ago=10)
    stuck2 = make_stuck_job("job-b", minutes_ago=20)
    stuck3 = make_stuck_job("job-c", minutes_ago=30)

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [stuck1, stuck2, stuck3]
    enqueue_fn = MagicMock()

    result = requeue_stuck_jobs(db, enqueue_fn, threshold_seconds=60)

    for job in [stuck1, stuck2, stuck3]:
        assert job.status == JobStatus.queued

    assert enqueue_fn.call_count == 3
    db.commit.assert_called_once()
    assert set(result) == {"job-a", "job-b", "job-c"}

# Test 4: only one commit regardless of how many jobs are re-queued
def test_single_commit_for_all_stuck_jobs():
    jobs = [make_stuck_job(f"job-{i}", minutes_ago=5) for i in range(5)]

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = jobs
    enqueue_fn = MagicMock()

    requeue_stuck_jobs(db, enqueue_fn, threshold_seconds=60)

    db.commit.assert_called_once()

# Test 5: worker calls requeue_stuck_jobs on the right cycle interval
def test_worker_calls_recovery_at_correct_interval():
    from app.workers.worker import process_jobs

    mock_redis = MagicMock()
    mock_redis.brpop.return_value = None

    with patch("app.workers.worker.get_redis", return_value=mock_redis), \
         patch("app.workers.worker.get_settings") as mock_settings, \
         patch("app.workers.worker.update_heartbeat"), \
         patch("app.workers.worker.requeue_stuck_jobs") as mock_recovery, \
         patch("app.workers.worker.SessionLocal") as mock_session:

        mock_settings.return_value.worker_heartbeat_ttl = 30
        mock_settings.return_value.stuck_check_interval = 5
        mock_settings.return_value.stuck_job_threshold = 60
        mock_session.return_value.__enter__ = MagicMock()

        process_jobs(max_iterations=10)

    assert mock_recovery.call_count == 2
