from app.models.job import Job, JobStatus
from sqlalchemy.orm import Session

def create_job(db: Session, payload: dict, idempotency_key: str = None):
    if idempotency_key:
        existing = db.query(Job).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    job = Job(
        payload=payload,
        status=JobStatus.queued,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job