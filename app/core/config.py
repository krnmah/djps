from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded in this priority order:
      1. Real environment variables (e.g. set by Docker Compose)
      2. .env file (used for local development)
      3. Default values defined below (last resort fallback)

    This means:
    - Local dev  → .env sets DATABASE_URL=...@localhost...
    - Docker     → docker-compose environment: overrides with @postgres/@redis
    """
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DJPS"
    database_url: str = "postgresql+psycopg2://djps:djps@localhost:5432/djps"
    redis_url: str = "redis://localhost:6379/0"

    # simulate external HTTP call settings
    # url that the worker will call to simulate
    simulated_job_url: str = "https://httpbin.org/delay/1"

    # Used to test retry or backoff logic later
    simulated_failure_rate: float = 0.2

    # timeout for the simulated call
    simulated_timeout: float = 5.0

@lru_cache
def get_settings() -> Settings:
    return Settings()