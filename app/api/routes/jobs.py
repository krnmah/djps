from fastapi import APIRouter, HTTPException, Request, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import uuid
import logging

from app.schemas.job import JobCreate, JobResponse
from app.models.job import Job, JobStatus
from app.api.deps import get_db
from app.queue.producer import enqueue_job
from app.core.limiter import limiter, rate_limit_str
from app.metrics.metrics import JOBS_CREATED

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
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
