from datetime import datetime, timezone

# Redis key pattern: worker:heartbeat:<worker_id>
HEARTBEAT_PREFIX = "worker:heartbeat:"


def update_heartbeat(worker_id: str, r, ttl: int) -> None:
    key = f"{HEARTBEAT_PREFIX}{worker_id}"
    value = datetime.now(timezone.utc).isoformat()
    r.setex(key, ttl, value)
