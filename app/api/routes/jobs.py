import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.limiter import limiter, rate_limit_str
from app.models.job import JobStatus
from app.schemas.job import JobCreate, JobListResponse, JobResponse
from app.services.job_service import (
    DuplicateIdempotencyKeyError,
    create_job as svc_create_job,
    get_job_by_id,
    list_jobs as svc_list_jobs,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(20, ge=1, le=100, description="Page size (1-100)"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    return svc_list_jobs(db, status=status, limit=limit, offset=offset)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = get_job_by_id(db, job_id)
    if not job:
        logger.warning("Job not found.", extra={"job_id": str(job_id)})
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(rate_limit_str)
def create_job(request: Request, job_in: JobCreate, db: Session = Depends(get_db)):
    try:
        return svc_create_job(
            db,
            payload=job_in.payload,
            job_type=job_in.type,
            idempotency_key=job_in.idempotency_key,
        )
    except DuplicateIdempotencyKeyError:
        raise HTTPException(status_code=409, detail="Duplicate idempotency key")
    except Exception as e:
        logger.error("Failed to create job.", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to create job")
