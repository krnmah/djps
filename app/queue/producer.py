from app.queue.redis_client import get_redis

QUEUE_NAME = "main_queue"
DLQ_NAME = "dead_letter_queue"


def enqueue_job(job_id: str) -> None:
    r = get_redis()
    r.lpush(QUEUE_NAME, job_id)


def push_to_dlq(job_id: str) -> None:
    r = get_redis()
    r.rpush(DLQ_NAME, job_id)