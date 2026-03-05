from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime
import uuid


class JobCreate(BaseModel):
    payload: dict = Field(..., description="Job payload (arbitrary JSON)")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key to prevent duplicate jobs")


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    payload: dict
    retry_count: int
    idempotency_key: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_attempt_at: Optional[datetime]


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    limit: int
    offset: int