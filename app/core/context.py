from contextvars import ContextVar

# current job being processed
job_id_var: ContextVar[str] = ContextVar("job_id", default="")

# worker identity
worker_id_var: ContextVar[str] = ContextVar("worker_id", default="")
