import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.api.deps import get_db
from app.models.base import Base
from app.core.config import get_settings

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
def limited_app():
    saved = {
        "RATE_LIMIT_PER_MINUTE": os.environ.get("RATE_LIMIT_PER_MINUTE"),
        "REDIS_URL": os.environ.get("REDIS_URL"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
    }

    os.environ["RATE_LIMIT_PER_MINUTE"] = "2"
    os.environ["REDIS_URL"] = TEST_REDIS_URL
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    get_settings.cache_clear()

    test_app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    test_app.dependency_overrides[get_db] = override_get_db

    yield TestClient(test_app)

    # restore
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


# Test 1: third request from the same IP is blocked with 429
def test_third_request_is_rate_limited(limited_app):
    ip = "10.14.0.1"
    headers = {"X-Forwarded-For": ip}

    r1 = limited_app.post("/jobs", json={"payload": {"t": "rl-1a"}}, headers=headers)
    r2 = limited_app.post("/jobs", json={"payload": {"t": "rl-1b"}}, headers=headers)
    r3 = limited_app.post("/jobs", json={"payload": {"t": "rl-1c"}}, headers=headers)

    assert r1.status_code == 201, f"1st request should be 201, got {r1.status_code}"
    assert r2.status_code == 201, f"2nd request should be 201, got {r2.status_code}"
    assert r3.status_code == 429, f"3rd request should be 429, got {r3.status_code}"

# Test 2: different IP is not affected by another IP's counter
def test_different_ip_is_not_affected(limited_app):
    ip_a = "10.14.0.2"
    ip_b = "10.14.0.3"

    limited_app.post("/jobs", json={"payload": {"t": "rl-2a"}}, headers={"X-Forwarded-For": ip_a})
    limited_app.post("/jobs", json={"payload": {"t": "rl-2b"}}, headers={"X-Forwarded-For": ip_a})
    blocked = limited_app.post("/jobs", json={"payload": {"t": "rl-2c"}}, headers={"X-Forwarded-For": ip_a})
    assert blocked.status_code == 429

    r = limited_app.post("/jobs", json={"payload": {"t": "rl-2d"}}, headers={"X-Forwarded-For": ip_b})
    assert r.status_code == 201, f"Different IP should not be rate-limited, got {r.status_code}"

# Test 3: GET /jobs/{id} is not rate-limited
def test_get_endpoint_is_not_rate_limited(limited_app):
    fake_id = str(uuid.uuid4())
    ip = "10.14.0.4"
    headers = {"X-Forwarded-For": ip}

    for _ in range(5):
        r = limited_app.get(f"/jobs/{fake_id}", headers=headers)
        assert r.status_code == 404, f"GET should be 404 (not rate-limited), got {r.status_code}"
