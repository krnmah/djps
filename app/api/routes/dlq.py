from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.job import JobResponse
from app.services.dlq_service import get_dlq_jobs

router = APIRouter()


@router.get("/dlq", response_model=List[JobResponse])
def get_dlq(db: Session = Depends(get_db)):
    return get_dlq_jobs(db)

