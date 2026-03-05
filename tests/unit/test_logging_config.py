import json
import logging
import pytest

from app.core.logging_config import StructuredJsonFormatter, setup_logging
from app.core.context import job_id_var, worker_id_var


def _make_record(msg: str, level=logging.INFO, name="test.logger", **extra_kwargs) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra_kwargs.items():
        setattr(record, k, v)
    return record


@pytest.fixture(autouse=True)
def reset_context_vars():
    job_id_var.set("")
    worker_id_var.set("")
    yield
    job_id_var.set("")
    worker_id_var.set("")


# Test 1: output is valid JSON
def test_formatter_produces_valid_json():
    formatter = StructuredJsonFormatter()
    record = _make_record("hello world")
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["message"] == "hello world"

# Test 2: required fields are present
def test_formatter_contains_required_fields():
    formatter = StructuredJsonFormatter()
    record = _make_record("test msg")
    parsed = json.loads(formatter.format(record))
    assert "timestamp" in parsed
    assert "level" in parsed
    assert "logger" in parsed
    assert "message" in parsed

# Test 3: job_id from ContextVar is injected automatically
def test_formatter_injects_job_id_from_context_var():
    job_id_var.set("abc-123")
    formatter = StructuredJsonFormatter()
    record = _make_record("processing job")
    parsed = json.loads(formatter.format(record))
    assert parsed["job_id"] == "abc-123"

# Test 4: worker_id from ContextVar is injected automatically
def test_formatter_injects_worker_id_from_context_var():
    worker_id_var.set("worker-xyz")
    formatter = StructuredJsonFormatter()
    record = _make_record("worker tick")
    parsed = json.loads(formatter.format(record))
    assert parsed["worker_id"] == "worker-xyz"

# Test 5: extra fields passed to the logger call appear in JSON
def test_formatter_includes_extra_fields():
    formatter = StructuredJsonFormatter()
    record = _make_record("retry event", retry_count=2, backoff_seconds=4.0)
    parsed = json.loads(formatter.format(record))
    assert parsed["retry_count"] == 2
    assert parsed["backoff_seconds"] == 4.0

# Test 6: no job_id key when context var is empty
def test_formatter_omits_job_id_when_not_set():
    formatter = StructuredJsonFormatter()
    record = _make_record("no context")
    parsed = json.loads(formatter.format(record))
    assert "job_id" not in parsed


# Test 7: exception info is serialised into "exception" field
def test_formatter_includes_exception():
    formatter = StructuredJsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

    record = _make_record("something went wrong", level=logging.ERROR)
    record.exc_info = exc_info
    parsed = json.loads(formatter.format(record))
    assert "exception" in parsed
    assert "ValueError" in parsed["exception"]

# Test 8: setup_logging attaches a handler with StructuredJsonFormatter
def test_setup_logging_attaches_json_handler():
    setup_logging("DEBUG")
    root = logging.getLogger()
    assert len(root.handlers) >= 1
    assert any(
        isinstance(h.formatter, StructuredJsonFormatter)
        for h in root.handlers
    )
    assert root.level == logging.DEBUG
