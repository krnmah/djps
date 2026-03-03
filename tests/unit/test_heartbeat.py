from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.workers.heartbeat import update_heartbeat, HEARTBEAT_PREFIX


# Test 1: correct Redis key is used
def test_heartbeat_uses_correct_key():
    mock_redis = MagicMock()
    update_heartbeat("worker-abc", mock_redis, ttl=30)

    key_used = mock_redis.setex.call_args[0][0]
    assert key_used == f"{HEARTBEAT_PREFIX}worker-abc"

# Test 2: setex is called with the configured TTL
def test_heartbeat_uses_configured_ttl():
    mock_redis = MagicMock()
    update_heartbeat("worker-xyz", mock_redis, ttl=45)

    ttl_used = mock_redis.setex.call_args[0][1]
    assert ttl_used == 45

# Test 3: the stored value is a valid utc timestamp
def test_heartbeat_value_is_iso_timestamp():
    mock_redis = MagicMock()
    update_heartbeat("worker-ts", mock_redis, ttl=30)

    value = mock_redis.setex.call_args[0][2]
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None

# Test 4: value is recent (within a few seconds of now)
def test_heartbeat_value_is_current_time():
    mock_redis = MagicMock()
    before = datetime.now(timezone.utc)
    update_heartbeat("worker-time", mock_redis, ttl=30)
    after = datetime.now(timezone.utc)

    value = mock_redis.setex.call_args[0][2]
    written = datetime.fromisoformat(value)

    assert before <= written <= after

# Test 5: different worker IDs produce different keys
def test_different_worker_ids_produce_different_keys():
    mock_redis = MagicMock()
    update_heartbeat("worker-1", mock_redis, ttl=30)
    update_heartbeat("worker-2", mock_redis, ttl=30)

    calls = mock_redis.setex.call_args_list
    key1 = calls[0][0][0]
    key2 = calls[1][0][0]

    assert key1 != key2
    assert key1 == f"{HEARTBEAT_PREFIX}worker-1"
    assert key2 == f"{HEARTBEAT_PREFIX}worker-2"

# Test 6: called on every worker loop cycle
def test_worker_calls_heartbeat_every_cycle():
    from app.workers.worker import process_jobs

    mock_redis = MagicMock()
    mock_redis.brpop.return_value = None

    with patch("app.workers.worker.get_redis", return_value=mock_redis), \
         patch("app.workers.worker.get_settings") as mock_settings, \
         patch("app.workers.worker.update_heartbeat") as mock_heartbeat:

        mock_settings.return_value.worker_heartbeat_ttl = 30
        process_jobs(max_iterations=3)

    assert mock_heartbeat.call_count == 3
