from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.job import Job
from app.queue.producer import DLQ_NAME
from app.queue.redis_client import get_redis

logger = logging.getLogger(__name__)


def get_dlq_jobs(db: Session) -> List[Job]:
    r = get_redis()
    job_ids = r.lrange(DLQ_NAME, 0, -1)

    jobs: List[Job] = []
    for job_id in job_ids:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            jobs.append(job)
        else:
            logger.warning(
                "DLQ entry has no matching DB row.",
                extra={"job_id": str(job_id)},
            )

    logger.info("DLQ listed.", extra={"count": len(jobs)})
    return jobs
