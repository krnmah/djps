from app.queue.redis_client import get_redis

QUEUE_NAME = "main_queue"

def enqueue_job(job_id: str):
    r = get_redis()
    r.lpush(QUEUE_NAME, job_id)