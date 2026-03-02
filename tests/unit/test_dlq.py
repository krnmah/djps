from unittest.mock import MagicMock, patch

from app.queue.producer import push_to_dlq, DLQ_NAME


# Test 1: push_to_dlq calls rpush with the correct queue name and job id
def test_push_to_dlq_uses_rpush():
    mock_redis = MagicMock()

    with patch("app.queue.producer.get_redis", return_value=mock_redis):
        push_to_dlq("job-abc-123")

    mock_redis.rpush.assert_called_once_with(DLQ_NAME, "job-abc-123")


# Test 2: Multiple failed jobs each get their own rpush call
def test_push_to_dlq_called_separately_for_each_job():
    mock_redis = MagicMock()

    with patch("app.queue.producer.get_redis", return_value=mock_redis):
        push_to_dlq("job-1")
        push_to_dlq("job-2")

    assert mock_redis.rpush.call_count == 2
    calls = [c.args for c in mock_redis.rpush.call_args_list]
    assert (DLQ_NAME, "job-1") in calls
    assert (DLQ_NAME, "job-2") in calls


# Test 3: DLQ_NAME constant is correct
def test_dlq_name_constant():
    assert DLQ_NAME == "dead_letter_queue"


# Test 4: retry_service calls dlq_fn (not enqueue_fn) on permanent failure
def test_retry_service_sends_to_dlq_on_permanent_failure():
    from app.services.retry_service import handle_job_failure
    from app.models.job import JobStatus

    db = MagicMock()
    enqueue_fn = MagicMock()
    dlq_fn = MagicMock()

    job = MagicMock()
    job.id = "failing-job-id"
    job.retry_count = 2
    job.status = JobStatus.processing

    with patch("app.services.retry_service.get_settings") as mock_settings, \
         patch("app.services.retry_service.time.sleep"):
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0
        handle_job_failure(db, job, enqueue_fn, dlq_fn)

    assert job.status == JobStatus.failed
    dlq_fn.assert_called_once_with("failing-job-id")
    enqueue_fn.assert_not_called()


# Test 5: retry_service does NOT call dlq_fn while still retrying
def test_retry_service_does_not_send_to_dlq_while_retrying():
    from app.services.retry_service import handle_job_failure
    from app.models.job import JobStatus

    db = MagicMock()
    enqueue_fn = MagicMock()
    dlq_fn = MagicMock()

    job = MagicMock()
    job.id = "retrying-job-id"
    job.retry_count = 0
    job.status = JobStatus.processing

    with patch("app.services.retry_service.get_settings") as mock_settings, \
         patch("app.services.retry_service.time.sleep"):
        mock_settings.return_value.max_job_retries = 3
        mock_settings.return_value.backoff_base = 2.0
        mock_settings.return_value.max_backoff = 60.0
        handle_job_failure(db, job, enqueue_fn, dlq_fn)

    enqueue_fn.assert_called_once_with("retrying-job-id")
    dlq_fn.assert_not_called()
