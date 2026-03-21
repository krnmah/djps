from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from datetime import datetime
import uuid


class JobOptions(BaseModel):
    timeout_seconds: Optional[int] = Field(None, ge=1, description="Optional per-job timeout override in seconds")
    max_retries: Optional[int] = Field(None, ge=0, description="Optional per-job retry override")
    priority: Optional[str] = Field(None, description="Optional priority hint (low/normal/high)")


class JobCreate(BaseModel):
    type: Literal["http_request", "email_send"] = Field(
        "http_request",
        description="Job type (http_request or email_send)",
    )
    payload: dict = Field(..., description="Job payload (arbitrary JSON)")
    options: Optional[JobOptions] = Field(None, description="Optional per-job execution options")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key to prevent duplicate jobs")


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: Optional[str] = None
    status: str
    payload: dict
    retry_count: int
    idempotency_key: Optional[str]
    result_json: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    last_attempt_at: Optional[datetime]
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    limit: int
    offset: int