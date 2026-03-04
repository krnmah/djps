import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prometheus_client import start_http_server
from app.workers.worker import process_jobs

if __name__ == "__main__":
    # Exposing worker side prometheus metrics on port 8001
    # so Prometheus can scrape JOBS_COMPLETED, JOBS_FAILED, JOBS_RETRIED from the worker process.
    start_http_server(8001)
    process_jobs()