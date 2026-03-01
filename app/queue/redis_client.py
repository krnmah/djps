import redis
from app.core.config import get_settings


def get_redis():
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)