import logging
import time
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.core.config import get_settings
from app.services.backoff import calculate_backoff
from app.metrics.metrics import JOBS_RETRIED, JOBS_FAILED

logger = logging.getLogger(__name__)


def handle_job_failure(db: Session, job: Job, enqueue_fn, dlq_fn) -> None:
    settings = get_settings()

    job.retry_count += 1

    if job.retry_count < settings.max_job_retries:
        # Calculate how long to wait before the next attempt.
        delay = calculate_backoff(
            retry_count=job.retry_count,
            base=settings.backoff_base,
            max_backoff=settings.max_backoff,
        )
        job.status = JobStatus.queued
        db.commit()
        JOBS_RETRIED.inc()
        logger.info(
            "Job re-queued for retry.",
            extra={
                "job_id": str(job.id),
                "retry_count": job.retry_count,
                "max_retries": settings.max_job_retries - 1,
                "backoff_seconds": delay,
            },
        )
        time.sleep(delay)
        enqueue_fn(str(job.id))
    else:
        job.status = JobStatus.failed
        db.commit()
        JOBS_FAILED.inc()
        dlq_fn(str(job.id))
        logger.error(
            "Job permanently failed, sent to DLQ.",
            extra={"job_id": str(job.id), "retry_count": job.retry_count},
        )
