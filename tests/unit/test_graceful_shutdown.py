import signal
from unittest.mock import MagicMock, patch, call

# Helpers
def _reset_shutdown(monkeypatch):
    """Clear the module-level _shutdown event before each test."""
    import app.workers.worker as wm
    monkeypatch.setattr(wm, "_shutdown", __import__("threading").Event())
    return wm._shutdown


# Test 1 — request_shutdown sets the event
def test_request_shutdown_sets_event(monkeypatch):
    shutdown_event = _reset_shutdown(monkeypatch)
    assert not shutdown_event.is_set()

    from app.workers.worker import request_shutdown
    request_shutdown(signum=signal.SIGTERM, frame=None)

    assert shutdown_event.is_set()


def test_request_shutdown_is_idempotent(monkeypatch):
    _reset_shutdown(monkeypatch)

    from app.workers.worker import request_shutdown
    request_shutdown()
    request_shutdown()

# Test 2 — process_jobs exits immediately when shutdown flag is pre-set
def test_process_jobs_exits_when_shutdown_pre_set(monkeypatch):
    import app.workers.worker as wm
    shutdown_event = _reset_shutdown(monkeypatch)
    shutdown_event.set()

    mock_redis = MagicMock()
    mock_redis.brpop.return_value = None

    with (
        patch("app.workers.worker.get_redis", return_value=mock_redis),
        patch("app.workers.worker.update_heartbeat"),
        patch("app.workers.worker.requeue_stuck_jobs"),
        patch("app.workers.worker.execute_job") as mock_execute,
        patch("app.workers.worker.SessionLocal"),
    ):
        wm.process_jobs(max_iterations=10)

    mock_redis.brpop.assert_not_called()
    mock_execute.assert_not_called()

# Test 3 — in-progress job completes before shutdown is honoured
def test_in_progress_job_completes_before_shutdown(monkeypatch):
    import app.workers.worker as wm
    shutdown_event = _reset_shutdown(monkeypatch)

    executed_jobs = []

    def fake_execute(job_id):
        shutdown_event.set()
        executed_jobs.append(job_id)

    mock_redis = MagicMock()
    mock_redis.brpop.side_effect = [
        ("main_queue", "job-abc"),
        None,
    ]

    mock_job = MagicMock()
    mock_job.id = "job-abc"
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_session.query.return_value.filter.return_value.first.return_value = mock_job

    with (
        patch("app.workers.worker.get_redis", return_value=mock_redis),
        patch("app.workers.worker.update_heartbeat"),
        patch("app.workers.worker.requeue_stuck_jobs"),
        patch("app.workers.worker.execute_job", side_effect=fake_execute),
        patch("app.workers.worker.SessionLocal", return_value=mock_session),
        patch("app.workers.worker.JOBS_COMPLETED"),
    ):
        wm.process_jobs(max_iterations=10)

    assert executed_jobs == ["job-abc"]
    assert mock_redis.brpop.call_count == 1

# Test 4 — WorkerManager.stop() uses SIGTERM with a grace period
def test_manager_stop_terminates_then_joins(monkeypatch):
    from app.workers.manager import WorkerManager

    manager = WorkerManager(num_workers=2, max_iterations=1)

    live_proc = MagicMock()
    live_proc.is_alive.return_value = True

    dead_proc = MagicMock()
    dead_proc.is_alive.return_value = False

    manager._processes = [live_proc, dead_proc]

    live_proc.join.side_effect = lambda timeout=None: setattr(
        live_proc, "_alive_after_join", False
    )
    live_proc.is_alive.side_effect = [True, False]

    manager.stop(grace_period=5.0)

    live_proc.terminate.assert_called_once()
    dead_proc.terminate.assert_not_called()
    live_proc.join.assert_called_once_with(timeout=5.0)
    assert len(manager._processes) == 0


def test_manager_stop_force_kills_after_grace_period(monkeypatch):
    from app.workers.manager import WorkerManager

    manager = WorkerManager(num_workers=1, max_iterations=1)

    stubborn_proc = MagicMock()
    stubborn_proc.is_alive.side_effect = [True, True]
    stubborn_proc.join.return_value = None

    manager._processes = [stubborn_proc]

    manager.stop(grace_period=0.1)

    stubborn_proc.terminate.assert_called_once()
    stubborn_proc.kill.assert_called_once()
    assert len(manager._processes) == 0


def test_manager_stop_clears_process_list():
    from app.workers.manager import WorkerManager

    manager = WorkerManager(num_workers=2, max_iterations=1)
    for _ in range(2):
        p = MagicMock()
        p.is_alive.return_value = False
        manager._processes.append(p)

    manager.stop()

    assert manager._processes == []

# Test — worker skips gracefully when job_id exists in Redis but not in the DB
def test_worker_skips_job_not_found_in_db(monkeypatch):
    import app.workers.worker as wm

    _reset_shutdown(monkeypatch)

    mock_redis = MagicMock()
    mock_redis.brpop.return_value = ("main_queue", "ghost-id-999")

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None

    with (
        patch("app.workers.worker.get_redis", return_value=mock_redis),
        patch("app.workers.worker.update_heartbeat"),
        patch("app.workers.worker.requeue_stuck_jobs"),
        patch("app.workers.worker.execute_job") as mock_execute,
        patch("app.workers.worker.SessionLocal", return_value=mock_session),
    ):
        wm.process_jobs(max_iterations=1)

    mock_execute.assert_not_called()
    mock_session.close.assert_called()
