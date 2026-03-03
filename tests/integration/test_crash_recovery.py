import os
from datetime import datetime, timedelta, timezone

import pytest
import redis as redis_lib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.models.base import Base
from app.models.job import Job, JobStatus
from app.queue.producer import QUEUE_NAME
from app.workers.recovery import requeue_stuck_jobs

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()

@pytest.fixture
def test_redis():
    r = redis_lib.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    r.delete(QUEUE_NAME)
    yield r
    r.delete(QUEUE_NAME)


# Test 1: stuck job is re-queued back onto main_queue
def test_stuck_job_is_requeued_to_redis(db, test_redis):
    stuck_job = Job(
        payload={"task": "crashed"},
        status=JobStatus.processing,
        last_attempt_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db.add(stuck_job)
    db.commit()
    db.refresh(stuck_job)
    job_id = str(stuck_job.id)

    def enqueue_fn(jid):
        test_redis.lpush(QUEUE_NAME, jid)

    requeued = requeue_stuck_jobs(db, enqueue_fn, threshold_seconds=60)

    assert job_id in requeued
    db.refresh(stuck_job)
    assert stuck_job.status == JobStatus.queued

    queue_contents = test_redis.lrange(QUEUE_NAME, 0, -1)
    assert job_id in queue_contents

# Test 2: fresh processing job is not stuck
def test_recent_processing_job_is_not_requeued(db, test_redis):
    fresh_job = Job(
        payload={"task": "in-progress"},
        status=JobStatus.processing,
        last_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    db.add(fresh_job)
    db.commit()
    db.refresh(fresh_job)
    job_id = str(fresh_job.id)

    requeued = requeue_stuck_jobs(db, lambda jid: test_redis.lpush(QUEUE_NAME, jid), threshold_seconds=3600)

    assert job_id not in requeued
    db.refresh(fresh_job)
    assert fresh_job.status == JobStatus.processing

# Test 3: completed / failed jobs are never touched
def test_completed_and_failed_jobs_ignored(db):
    completed = Job(
        payload={"t": "done"},
        status=JobStatus.completed,
        last_attempt_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    failed = Job(
        payload={"t": "fail"},
        status=JobStatus.failed,
        last_attempt_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db.add_all([completed, failed])
    db.commit()

    requeued = requeue_stuck_jobs(db, lambda jid: test_redis.lpush(QUEUE_NAME, jid), threshold_seconds=60)

    completed_id = str(completed.id)
    failed_id = str(failed.id)
    assert completed_id not in requeued
    assert failed_id not in requeued
