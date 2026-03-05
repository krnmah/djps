import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)


def requeue_stuck_jobs(db: Session, enqueue_fn, threshold_seconds: int) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)

    cutoff_naive = cutoff.replace(tzinfo=None)
    
    stuck_jobs = (
        db.query(Job)
        .filter(
            Job.status == JobStatus.processing,
            Job.last_attempt_at < cutoff_naive,
        )
        .all()
    )

    requeued = []
    for job in stuck_jobs:
        job.status = JobStatus.queued
        requeued.append(str(job.id))
        logger.warning(
            "Stuck job detected, re-queuing.",
            extra={"job_id": str(job.id), "last_attempt_at": str(job.last_attempt_at)},
        )

    if requeued:
        db.commit()
        for job_id in requeued:
            enqueue_fn(job_id)

    return requeued
