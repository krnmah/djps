import pytest
from unittest.mock import MagicMock, patch


# Job.__repr__
def test_job_repr_contains_id_and_status():
    from app.models.job import Job, JobStatus

    job = Job(payload={"x": 1}, status=JobStatus.queued)
    result = repr(job)

    assert "Job" in result
    assert "queued" in result

# app.api.deps.get_db — generator yields session and closes on exit
def test_deps_get_db_yields_session_then_closes():
    from app.api.deps import get_db

    mock_session = MagicMock()
    with patch("app.api.deps.SessionLocal", return_value=mock_session):
        gen = get_db()
        yielded = next(gen)

        assert yielded is mock_session

        with pytest.raises(StopIteration):
            next(gen)

    mock_session.close.assert_called_once()

def test_deps_get_db_closes_on_exception():
    from app.api.deps import get_db

    mock_session = MagicMock()
    with patch("app.api.deps.SessionLocal", return_value=mock_session):
        gen = get_db()
        next(gen)
        try:
            gen.throw(RuntimeError("consumer error"))
        except RuntimeError:
            pass

    mock_session.close.assert_called_once()

# app.db.session.get_db — same contract
def test_session_get_db_yields_session_then_closes():
    from app.db.session import get_db

    mock_session = MagicMock()
    with patch("app.db.session.SessionLocal", return_value=mock_session):
        gen = get_db()
        yielded = next(gen)

        assert yielded is mock_session

        with pytest.raises(StopIteration):
            next(gen)

    mock_session.close.assert_called_once()

def test_session_get_db_closes_on_exception():
    from app.db.session import get_db

    mock_session = MagicMock()
    with patch("app.db.session.SessionLocal", return_value=mock_session):
        gen = get_db()
        next(gen)
        try:
            gen.throw(RuntimeError("consumer error"))
        except RuntimeError:
            pass

    mock_session.close.assert_called_once()

# POST /jobs — unexpected service error → HTTP 500
def test_create_job_route_returns_500_on_unexpected_error():
    from fastapi import HTTPException
    from starlette.requests import Request as StarletteRequest
    from app.api.routes.jobs import create_job
    from app.schemas.job import JobCreate

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/jobs",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 8000),
    }
    request = StarletteRequest(scope)
    job_in = JobCreate(payload={"task": "boom"})
    mock_db = MagicMock()

    with patch(
        "app.api.routes.jobs.svc_create_job",
        side_effect=RuntimeError("database exploded"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            create_job(request=request, job_in=job_in, db=mock_db)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to create job"

# DuplicateIdempotencyKeyError → HTTP 409
def test_create_job_route_returns_409_on_duplicate_key():
    from fastapi import HTTPException
    from starlette.requests import Request as StarletteRequest
    from app.api.routes.jobs import create_job
    from app.schemas.job import JobCreate
    from app.services.job_service import DuplicateIdempotencyKeyError

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/jobs",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 8000),
    }
    request = StarletteRequest(scope)
    job_in = JobCreate(payload={"task": "dup"}, idempotency_key="dup-key")
    mock_db = MagicMock()

    with patch(
        "app.api.routes.jobs.svc_create_job",
        side_effect=DuplicateIdempotencyKeyError("dup-key"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            create_job(request=request, job_in=job_in, db=mock_db)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Duplicate idempotency key"
