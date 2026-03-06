import uuid

from sqlalchemy import (
    Column, Index, String, DateTime, Enum, Integer, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.models.base import Base

class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payload = Column(JSONB, nullable=False)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.queued)
    retry_count = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    last_attempt_at = Column(DateTime, nullable=True)

    # indexes
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_status_created_at", "status", "created_at"),
        Index("idx_jobs_last_attempt_at", "last_attempt_at"),
    )

    def __repr__(self):
        return f"<Job id={self.id} status={self.status}>"