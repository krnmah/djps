from fastapi import APIRouter, HTTPException, Query, Request, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
import uuid
import logging

from app.schemas.job import JobCreate, JobListResponse, JobResponse
from app.models.job import Job, JobStatus
from app.api.deps import get_db
from app.queue.producer import enqueue_job
from app.core.limiter import limiter, rate_limit_str
from app.metrics.metrics import JOBS_CREATED

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(20, ge=1, le=100, description="Page size (1-100)"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
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


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        logger.warning("Job not found.", extra={"job_id": str(job_id)})
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED
)
@limiter.limit(rate_limit_str)
def create_job(request: Request, job_in: JobCreate, db: Session = Depends(get_db)):
    try:
        if job_in.idempotency_key:
            existing = db.query(Job).filter_by(idempotency_key=job_in.idempotency_key).first()
            if existing:
                return existing

        job = Job(
            payload=job_in.payload,
            status=JobStatus.queued,
            idempotency_key=job_in.idempotency_key,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        enqueue_job(str(job.id))
        JOBS_CREATED.inc()
        logger.info("Job created.", extra={"job_id": str(job.id), "idempotency_key": job_in.idempotency_key})
        return job

    except IntegrityError:
        # Race condition: two concurrent requests with the same idempotency_key
        # both passed the idempotency check above
        db.rollback()
        existing = db.query(Job).filter_by(idempotency_key=job_in.idempotency_key).first()
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="Duplicate idempotency key")

    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job")
