from prometheus_client import Counter, Gauge, Histogram

# Counters
JOBS_CREATED = Counter(
    "djps_jobs_created_total",
    "Total number of jobs submitted via POST /jobs",
)

JOBS_COMPLETED = Counter(
    "djps_jobs_completed_total",
    "Total number of jobs that reached the 'completed' status",
)

JOBS_FAILED = Counter(
    "djps_jobs_failed_total",
    "Total number of jobs permanently moved to failed / DLQ",
)

JOBS_RETRIED = Counter(
    "djps_jobs_retried_total",
    "Total number of individual retry attempts",
)

QUEUE_DEPTH = Gauge(
    "djps_queue_depth",
    "Current number of jobs waiting in the main Redis queue",
    multiprocess_mode="livemax",
)

ACTIVE_WORKERS = Gauge(
    "djps_active_workers",
    "Number of worker processes currently running",
    multiprocess_mode="livesum",
)

JOB_DURATION = Histogram(
    "djps_job_duration_seconds",
    "Time (seconds) from job pick-up to completion or failure",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
