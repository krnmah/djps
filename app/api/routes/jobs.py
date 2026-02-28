from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.schemas.job import JobCreate, JobResponse
from app.models.job import Job, JobStatus
from app.db.session import get_db
import uuid

router = APIRouter()

@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED
)
def create_job(job_in: JobCreate, db: Session = Depends(get_db)):
    # check for idempotency
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
    return job