import multiprocessing
import os
import time

import pytest
import redis as redis_lib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.job import Job, JobStatus
from app.queue.producer import QUEUE_NAME
from app.workers.manager import _worker_target

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb",
)
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


# helpers
def spawn_workers(num_workers: int, max_iterations: int) -> list:
    processes = []
    for _ in range(num_workers):
        p = multiprocessing.Process(
            target=_worker_target,
            args=(TEST_DATABASE_URL, TEST_REDIS_URL, max_iterations, 0.0),
            daemon=True,
        )
        p.start()
        processes.append(p)
    return processes

def stop_workers(processes: list):
    for p in processes:
        if p.is_alive():
            p.terminate()
    for p in processes:
        p.join(timeout=5)

def wait_for_completion(db, job_ids: list[str], timeout: int = 30) -> dict | None:
    terminal = {JobStatus.completed, JobStatus.failed}
    deadline = time.time() + timeout
    while time.time() < deadline:
        db.expire_all()
        statuses = {
            str(j.id): j.status
            for j in db.query(Job).filter(Job.id.in_(job_ids)).all()
        }
        if all(s in terminal for s in statuses.values()):
            return statuses
        time.sleep(0.5)
    return None  # timed out


# Test 1: two workers drain all 10 jobs
def test_two_workers_process_all_jobs(db, test_redis):
    NUM_JOBS = 10
    NUM_WORKERS = 2
    MAX_ITER = 30

    jobs = [
        Job(payload={"task": f"concurrent_{i}"}, status=JobStatus.queued)
        for i in range(NUM_JOBS)
    ]
    db.add_all(jobs)
    db.commit()

    job_ids = [str(j.id) for j in jobs]
    for jid in job_ids:
        test_redis.lpush(QUEUE_NAME, jid)

    processes = spawn_workers(NUM_WORKERS, MAX_ITER)
    try:
        final_statuses = wait_for_completion(db, job_ids, timeout=40)
    finally:
        stop_workers(processes)

    assert final_statuses is not None, (
        "Timeout: not all jobs reached a terminal status within 40s"
    )

    for jid, status in final_statuses.items():
        assert status == JobStatus.completed, (
            f"Job {jid} ended with unexpected status={status}"
        )

# Test 2: Redis BRPOP atomicity — no job processed twice
def test_no_job_processed_twice(db, test_redis):
    NUM_JOBS = 6
    MAX_ITER = 20

    jobs = [
        Job(payload={"task": f"no_dup_{i}"}, status=JobStatus.queued)
        for i in range(NUM_JOBS)
    ]
    db.add_all(jobs)
    db.commit()

    job_ids = [str(j.id) for j in jobs]
    for jid in job_ids:
        test_redis.lpush(QUEUE_NAME, jid)

    processes = spawn_workers(2, MAX_ITER)
    try:
        final_statuses = wait_for_completion(db, job_ids, timeout=40)
    finally:
        stop_workers(processes)

    assert final_statuses is not None, "Timeout waiting for jobs to complete"

    db.expire_all()
    completed_jobs = db.query(Job).filter(Job.id.in_(job_ids)).all()
    for job in completed_jobs:
        assert job.status == JobStatus.completed, (
            f"Job {job.id} status={job.status}"
        )
        assert job.retry_count == 0, (
            f"Job {job.id} has retry_count={job.retry_count} — "
            "possible double-process or unexpected failure"
        )
