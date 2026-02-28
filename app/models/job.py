import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Enum, Integer, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
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

    def __repr__(self):
        return f"<Job id={self.id} status={self.status}>"