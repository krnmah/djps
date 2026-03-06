from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.queue.producer import enqueue_job
from app.metrics.metrics import JOBS_CREATED
from app.schemas.job import JobListResponse

logger = logging.getLogger(__name__)


class DuplicateIdempotencyKeyError(Exception):
    """Raised when an idempotency key collision cannot be resolved."""


def create_job(
    db: Session,
    payload: dict,
    idempotency_key: Optional[str] = None,
) -> Job:
    if idempotency_key:
        existing = db.query(Job).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            logger.info(
                "Idempotent job returned.",
                extra={"job_id": str(existing.id), "idempotency_key": idempotency_key},
            )
            return existing

    job = Job(
        payload=payload,
        status=JobStatus.queued,
        idempotency_key=idempotency_key,
    )
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        existing = db.query(Job).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing
        raise DuplicateIdempotencyKeyError(
            f"Duplicate idempotency key: {idempotency_key!r}"
        )

    enqueue_job(str(job.id))
    JOBS_CREATED.inc()
    logger.info(
        "Job created.",
        extra={"job_id": str(job.id), "idempotency_key": idempotency_key},
    )
    return job


def get_job_by_id(db: Session, job_id: uuid.UUID) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(
    db: Session,
    status: Optional[JobStatus] = None,
    limit: int = 20,
    offset: int = 0,
) -> JobListResponse:
    query = db.query(Job)
    if status is not None:
        query = query.filter(Job.status == status)
    total = query.count()
    items = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    logger.info(
        "Listed jobs.",
        extra={"status_filter": status, "limit": limit, "offset": offset, "total": total},
    )
    return JobListResponse(items=items, total=total, limit=limit, offset=offset)
