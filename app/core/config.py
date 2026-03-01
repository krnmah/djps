from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # max number of attempts before a job is permanently marked failed
    max_job_retries: int = 3

    # exponential backoff: delay = backoff_base ** retry_count (seconds)
    backoff_base: float = 2.0

    # hard ceiling on backoff delay so jobs don't wait > 1 minute
    max_backoff: float = 60.0

@lru_cache
def get_settings() -> Settings:
    return Settings()