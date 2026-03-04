from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.core.limiter import limiter


def create_app() -> FastAPI:
    app = FastAPI(
        title="DJPS",
        version="0.1.0",
    )

    # attach limiter to app state, add middleware and error handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(api_router)

    return app

app = create_app()