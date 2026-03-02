from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.dlq import router as dlq_router

api_router = APIRouter()

# Register route modules here
api_router.include_router(health_router, tags=["health"])
api_router.include_router(jobs_router, tags=["jobs"])
api_router.include_router(dlq_router, tags=["dlq"])