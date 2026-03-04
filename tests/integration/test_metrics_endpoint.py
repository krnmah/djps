import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.api.deps import get_db
from app.models.base import Base

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

@pytest.fixture(scope="module")
def client():
    saved_redis = os.environ.get("REDIS_URL")
    saved_db = os.environ.get("DATABASE_URL")
    os.environ["REDIS_URL"] = TEST_REDIS_URL
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from app.core.config import get_settings
    get_settings.cache_clear()

    app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield client

    for key, saved in [("REDIS_URL", saved_redis), ("DATABASE_URL", saved_db)]:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved
    get_settings.cache_clear()


# Test 1: /metrics returns 200 with Prometheus content-type
def test_metrics_endpoint_returns_200(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

# Test 2: response body contains our custom metric names
def test_metrics_contains_custom_counters(client):
    response = client.get("/metrics")
    body = response.text
    assert "djps_jobs_created_total" in body
    assert "djps_jobs_completed_total" in body
    assert "djps_jobs_failed_total" in body
    assert "djps_jobs_retried_total" in body

# Test 3: creating a job increments djps_jobs_created_total
def test_jobs_created_counter_increments(client):
    before_body = client.get("/metrics").text
    before = _parse_counter(before_body, "djps_jobs_created_total")

    client.post("/jobs", json={"payload": {"task": "metrics_test"}})

    after_body = client.get("/metrics").text
    after = _parse_counter(after_body, "djps_jobs_created_total")

    assert after == before + 1

# helpers
def _parse_counter(body: str, metric_name: str) -> float:
    for line in body.splitlines():
        if line.startswith(metric_name) and not line.startswith("#"):
            return float(line.split()[-1])
    return 0.0
