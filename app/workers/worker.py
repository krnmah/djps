import logging
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
from app.metrics.metrics import JOBS_COMPLETED

QUEUE_NAME = "main_queue"
logger = logging.getLogger(__name__)


def process_jobs(max_iterations: int = None):
    r = get_redis()
    settings = get_settings()

    # Unique ID for this worker process
    worker_id = str(uuid.uuid4())
    worker_id_var.set(worker_id)
    logger.info("Worker started.", extra={"worker_id": worker_id})

    iterations = 0
    while True:
        if max_iterations is not None and iterations >= max_iterations:
            break
        iterations += 1

        # Refresh heartbeat
        update_heartbeat(worker_id, r, ttl=settings.worker_heartbeat_ttl)

        # periodically scan for stuck jobs
        if iterations % settings.stuck_check_interval == 0:
            db = SessionLocal()
            try:
                requeue_stuck_jobs(db, enqueue_job, settings.stuck_job_threshold)
            finally:
                db.close()

        # BRPOP blocks until a job is available
        # like timeout = 5s then loops
        result = r.brpop(QUEUE_NAME, timeout=5)
        if result is None:
            # no jobs in 5s, loop again
            continue

        _, job_id = result
        job_id_var.set(job_id)
        logger.info("Picked up job.", extra={"job_id": job_id})

        db = SessionLocal()
        job = None
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

            # Execute the job (simulated HTTP call)
            execute_job(job_id)

            # Mark as completed
            job.status = JobStatus.completed
            db.commit()
            JOBS_COMPLETED.inc()
            logger.info("Job completed.", extra={"job_id": job_id})

        except Exception as e:
            logger.error("Job failed.", extra={"job_id": job_id, "error": str(e)})
            if job is not None:
                handle_job_failure(db, job, enqueue_job, push_to_dlq)
        finally:
            db.close()
    
if __name__ == "__main__":
    process_jobs()