from unittest.mock import patch, MagicMock
import pytest
import httpx
from app.services.job_executor import execute_job


def test_execute_job_simulated_failure():
    # always failure case
    with patch("app.services.job_executor.random.random", return_value=0.0):
        with pytest.raises(RuntimeError, match="simulated failure"):
            execute_job("test-job-id")


def test_execute_job_success():
    # never fails case
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("app.services.job_executor.random.random", return_value=1.0):
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            execute_job("test-job-id")


def test_execute_job_timeout():
    # timeout case
    with patch("app.services.job_executor.random.random", return_value=1.0):
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("timeout")
            with pytest.raises(httpx.TimeoutException):
                execute_job("test-job-id")