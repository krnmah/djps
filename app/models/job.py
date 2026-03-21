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

class JobType(str, enum.Enum):
    http_request = "http_request"
    email_send = "email_send"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(Enum(JobType), nullable=False, default=JobType.http_request)
    payload = Column(JSONB, nullable=False)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.queued)
    retry_count = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String, unique=True, nullable=True)
    result_json = Column(JSONB, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    last_attempt_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # indexes
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_status_created_at", "status", "created_at"),
        Index("idx_jobs_last_attempt_at", "last_attempt_at"),
        Index("idx_jobs_job_type_status_created_at", "job_type", "status", "created_at"),
    )

    def __repr__(self):
        return f"<Job id={self.id} status={self.status}>"