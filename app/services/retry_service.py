from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.core.config import get_settings


def handle_job_failure(db: Session, job: Job, enqueue_fn):
    settings = get_settings()

    job.retry_count += 1

    if job.retry_count < settings.max_job_retries:
        job.status = JobStatus.queued
        db.commit()
        enqueue_fn(str(job.id))
        print(
            f"Job {job.id} re-queued "
            f"(attempt {job.retry_count} of {settings.max_job_retries - 1} retries)"
        )
    else:
        job.status = JobStatus.failed
        db.commit()
        print(
            f"Job {job.id} permanently failed after {job.retry_count} attempt(s)."
        )
