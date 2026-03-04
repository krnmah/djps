from prometheus_client import Counter

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
