import logging
import signal
import threading
import time
import uuid
from datetime import datetime, timezone

from app.queue.redis_client import get_redis
from app.queue.producer import enqueue_job, push_to_dlq
from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.services.job_executor import execute_job
from app.services.retry_service import handle_job_failure
from app.workers.heartbeat import update_heartbeat
from app.workers.recovery import requeue_stuck_jobs
from app.core.config import get_settings
from app.core.context import job_id_var, worker_id_var
from app.metrics.metrics import JOBS_COMPLETED, QUEUE_DEPTH, ACTIVE_WORKERS, JOB_DURATION

QUEUE_NAME = "main_queue"
logger = logging.getLogger(__name__)
_shutdown = threading.Event()


def request_shutdown(signum=None, frame=None):
    logger.info(
        "Shutdown signal received, finishing current job then exiting.",
        extra={"signal": signum},
    )
    _shutdown.set()


def process_jobs(max_iterations: int = None):
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)

    r = get_redis()
    settings = get_settings()

    # Unique ID for this worker process
    worker_id = str(uuid.uuid4())
    worker_id_var.set(worker_id)
    logger.info("Worker started.", extra={"worker_id": worker_id})

    iterations = 0
    ACTIVE_WORKERS.inc()
    try:
        while True:
            if _shutdown.is_set():
                logger.info(
                    "Graceful shutdown: no more jobs will be picked up.",
                    extra={"worker_id": worker_id},
                )
                break

            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1

            # Refresh heartbeat
            update_heartbeat(worker_id, r, ttl=settings.worker_heartbeat_ttl)

            QUEUE_DEPTH.set(r.llen(QUEUE_NAME))

            # periodically scan for stuck jobs
            if iterations % settings.stuck_check_interval == 0:
                db = SessionLocal()
                try:
                    requeue_stuck_jobs(db, enqueue_job, settings.stuck_job_threshold)
                finally:
                    db.close()

            # Block up to 5 s waiting for a job; loop back if the queue is empty.
            result = r.brpop(QUEUE_NAME, timeout=5)
            if result is None:
                continue

            _, job_id = result
            job_id_var.set(job_id)
            logger.info("Picked up job.", extra={"job_id": job_id})

            db = SessionLocal()
            job = None
            _t0 = None
            try:
                job = db.query(Job).filter(Job.id == job_id).first()

                if not job:
                    logger.warning("Job not found in DB, skipping.", extra={"job_id": job_id})
                    db.close()
                    continue

                # Mark as processing
                job.status = JobStatus.processing
                job.last_attempt_at = datetime.now(timezone.utc)
                db.commit()

                # Execute the job and record duration.
                _t0 = time.perf_counter()
                execute_job(job_id)
                JOB_DURATION.observe(time.perf_counter() - _t0)

                # Mark as completed
                job.status = JobStatus.completed
                db.commit()
                JOBS_COMPLETED.inc()
                logger.info("Job completed.", extra={"job_id": job_id})

            except Exception as e:
                logger.error("Job failed.", extra={"job_id": job_id, "error": str(e)})
                if job is not None:
                    if _t0 is not None:
                        JOB_DURATION.observe(time.perf_counter() - _t0)
                    handle_job_failure(db, job, enqueue_job, push_to_dlq)
            finally:
                db.close()
    finally:
        ACTIVE_WORKERS.dec()


if __name__ == "__main__":
    process_jobs()