import os
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.job import Job, JobStatus

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://testuser:testpass@localhost:5433/testdb",
)

engine = create_engine(TEST_DATABASE_URL)
Session = sessionmaker(bind=engine)

BULK_SIZE = 2_000

# fixtures
@pytest.fixture(scope="module", autouse=True)
def setup_schema_and_bulk_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = Session()
    try:
        statuses = [JobStatus.queued, JobStatus.processing, JobStatus.completed, JobStatus.failed]
        rows = []
        for i in range(BULK_SIZE):
            rows.append(Job(
                payload={"task": f"bench-{i}", "index": i},
                status=statuses[i % len(statuses)],
                retry_count=i % 4,
            ))
        db.bulk_save_objects(rows)
        db.commit()

        with engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("ANALYZE jobs"))
    finally:
        db.close()

    yield

    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = Session()
    yield session
    session.close()


# helper: run EXPLAIN ANALYZE and return the plan as a string
def explain(db, sql: str, params: dict = None) -> str:
    result = db.execute(text(f"EXPLAIN ANALYZE {sql}"), params or {})
    return "\n".join(row[0] for row in result)

def uses_index_scan(plan: str) -> bool:
    plan_lower = plan.lower()
    return any(
        kw in plan_lower
        for kw in ("index scan", "index only scan", "bitmap index scan", "bitmap heap scan")
    )


# Test 1 — Verify indexes exist in the database
class TestIndexesExistInDb:
    def _pg_indexes(self, db) -> set:
        rows = db.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'jobs'")
        ).fetchall()
        return {row[0] for row in rows}

    def test_status_index_in_db(self, db):
        assert "idx_jobs_status" in self._pg_indexes(db)

    def test_created_at_index_in_db(self, db):
        assert "idx_jobs_created_at" in self._pg_indexes(db)

    def test_composite_index_in_db(self, db):
        assert "idx_jobs_status_created_at" in self._pg_indexes(db)

    def test_last_attempt_at_index_in_db(self, db):
        assert "idx_jobs_last_attempt_at" in self._pg_indexes(db)


# Test 2 — Verify query planner uses index scans
class TestQueryPlannerUsesIndexes:
    def test_status_filter_uses_index(self, db):
        plan = explain(
            db,
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at DESC LIMIT 20",
        )
        assert uses_index_scan(plan), (
            f"Expected index scan for status filter.\nPlan:\n{plan}"
        )

    def test_status_filter_explain_output(self, db):
        plan = explain(
            db,
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at DESC LIMIT 20",
        )
        print(f"\n--- EXPLAIN ANALYZE: status filter ---\n{plan}\n")

    def test_last_attempt_at_filter_uses_index(self, db):
        plan = explain(
            db,
            "SELECT * FROM jobs WHERE last_attempt_at IS NOT NULL",
        )
        assert uses_index_scan(plan), (
            f"Expected index scan for last_attempt_at filter.\nPlan:\n{plan}"
        )

    def test_full_list_order_by_created_at_uses_index(self, db):
        plan = explain(
            db,
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 20",
        )
        assert uses_index_scan(plan), (
            f"Expected index scan for ORDER BY created_at.\nPlan:\n{plan}"
        )


# Test 3 — ensure hot queries run within acceptable latency bounds
class TestQueryLatency:
    ITERATIONS = 200
    MAX_AVERAGE_MS = 10.0

    def _avg_ms(self, db, sql: str, params: dict = None) -> float:
        start = time.perf_counter()
        for _ in range(self.ITERATIONS):
            db.execute(text(sql), params or {}).fetchall()
        elapsed = time.perf_counter() - start
        return (elapsed / self.ITERATIONS) * 1000

    def test_status_filter_query_is_fast(self, db):
        avg = self._avg_ms(
            db,
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at DESC LIMIT 20",
        )
        print(f"\n  status filter avg: {avg:.3f} ms  (threshold: {self.MAX_AVERAGE_MS} ms)")
        assert avg < self.MAX_AVERAGE_MS, (
            f"status filter took {avg:.2f} ms avg (expected < {self.MAX_AVERAGE_MS} ms)"
        )

    def test_get_by_id_is_fast(self, db):
        first_id = db.execute(text("SELECT id FROM jobs LIMIT 1")).scalar()
        avg = self._avg_ms(
            db,
            "SELECT * FROM jobs WHERE id = :job_id",
            {"job_id": first_id},
        )
        print(f"\n  pk lookup avg: {avg:.3f} ms  (threshold: {self.MAX_AVERAGE_MS} ms)")
        assert avg < self.MAX_AVERAGE_MS, (
            f"PK lookup took {avg:.2f} ms avg (expected < {self.MAX_AVERAGE_MS} ms)"
        )

    def test_combined_status_created_at_query_is_fast(self, db):
        avg = self._avg_ms(
            db,
            "SELECT * FROM jobs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 10",
        )
        print(f"\n  composite index query avg: {avg:.3f} ms  (threshold: {self.MAX_AVERAGE_MS} ms)")
        assert avg < self.MAX_AVERAGE_MS, (
            f"Composite query took {avg:.2f} ms avg (expected < {self.MAX_AVERAGE_MS} ms)"
        )
