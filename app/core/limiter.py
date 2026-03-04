from starlette.requests import Request
from slowapi import Limiter


def get_client_ip(request: Request) -> str:
    # getting caller's IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

limiter = Limiter(key_func=get_client_ip)


def rate_limit_str() -> str:
    from app.core.config import get_settings
    return f"{get_settings().rate_limit_per_minute}/minute"
