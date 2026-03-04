import os
from unittest.mock import MagicMock

from app.core.limiter import get_client_ip, rate_limit_str
from app.core.config import get_settings

# helpers
def _make_request(forwarded: str = None, client_host: str = "127.0.0.1"):
    req = MagicMock()
    req.headers = {}
    if forwarded is not None:
        req.headers = {"X-Forwarded-For": forwarded}
    req.client = MagicMock()
    req.client.host = client_host
    return req

# get_client_ip
def test_get_client_ip_uses_forwarded_header():
    req = _make_request(forwarded="203.0.113.5")
    assert get_client_ip(req) == "203.0.113.5"


def test_get_client_ip_strips_whitespace_from_forwarded():
    req = _make_request(forwarded="  203.0.113.5  ")
    assert get_client_ip(req) == "203.0.113.5"


def test_get_client_ip_takes_first_from_chain():
    req = _make_request(forwarded="1.2.3.4, 5.6.7.8, 9.10.11.12")
    assert get_client_ip(req) == "1.2.3.4"


def test_get_client_ip_falls_back_to_client_host():
    req = _make_request(forwarded=None, client_host="10.0.0.99")
    assert get_client_ip(req) == "10.0.0.99"


def test_get_client_ip_no_client_returns_unknown():
    req = MagicMock()
    req.headers = {}
    req.client = None
    assert get_client_ip(req) == "unknown"


# rate_limit_str
def test_rate_limit_str_uses_settings_value():
    original = os.environ.get("RATE_LIMIT_PER_MINUTE")
    try:
        os.environ["RATE_LIMIT_PER_MINUTE"] = "42"
        get_settings.cache_clear()
        result = rate_limit_str()
        assert result == "42/minute"
    finally:
        if original is None:
            os.environ.pop("RATE_LIMIT_PER_MINUTE", None)
        else:
            os.environ["RATE_LIMIT_PER_MINUTE"] = original
        get_settings.cache_clear()


def test_rate_limit_str_default_is_60_per_minute():
    os.environ.pop("RATE_LIMIT_PER_MINUTE", None)
    get_settings.cache_clear()
    try:
        result = rate_limit_str()
        assert result == "60/minute"
    finally:
        get_settings.cache_clear()
