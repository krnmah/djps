import random
import httpx
from app.core.config import get_settings

def execute_job(job_id: str) -> None:
    # simulates processing a job
    settings = get_settings()

    # randomly simulate failure based on configured rate
    # like 0.2 means 20% of jobs will fail intentionally
    if random.random() < settings.simulated_failure_rate:
        raise RuntimeError(f"simulated failure for job {job_id}")
    
    # make a real HTTP call to simulate latency work
    with httpx.Client(timeout=settings.simulated_timeout) as client:
        response = client.get(settings.simulated_job_url)
        response.raise_for_status()