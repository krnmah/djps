import json
import logging

from app.core.context import job_id_var, worker_id_var

_SKIP_ATTRS = frozenset({
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "id", "levelname", "levelno", "lineno", "module", "msecs", "message",
    "msg", "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName",
})


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        job_id = job_id_var.get("")
        if job_id:
            log["job_id"] = job_id

        worker_id = worker_id_var.get("")
        if worker_id:
            log["worker_id"] = worker_id

        for key, val in record.__dict__.items():
            if key not in _SKIP_ATTRS and not key.startswith("_"):
                if key not in log:
                    log[key] = val

        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        return json.dumps(log, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for name in ("uvicorn.access", "sqlalchemy.engine", "urllib3", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)
