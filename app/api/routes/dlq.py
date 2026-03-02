from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.job import Job
from app.queue.producer import DLQ_NAME
from app.queue.redis_client import get_redis
from app.schemas.job import JobResponse

router = APIRouter()

@router.get("/dlq", response_model=List[JobResponse])
def get_dlq(db: Session = Depends(get_db)):
    r = get_redis()
    # get all dead jobs
    job_ids = r.lrange(DLQ_NAME, 0, -1)

    jobs = []
    for job_id in job_ids:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            jobs.append(job)

    return jobs
