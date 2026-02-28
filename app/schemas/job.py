from pydantic import BaseModel, Field
from typing import Any, Optional
import uuid

class JobCreate(BaseModel):
    payload: dict = Field(..., description="Job payload (arbitrary JSON)")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key to prevent duplicate jobs")

class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    payload: dict
    retry_count: int
    idempotency_key: Optional[str]