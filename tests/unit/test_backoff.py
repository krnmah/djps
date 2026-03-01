import pytest
from app.services.backoff import calculate_backoff

# Test the delay values at each retry count
def test_first_retry_delay():
    """retry_count=1, base=2 → 2^1 = 2.0s"""
    assert calculate_backoff(retry_count=1, base=2.0, max_backoff=60.0) == 2.0

def test_second_retry_delay():
    """retry_count=2, base=2 → 2^2 = 4.0s"""
    assert calculate_backoff(retry_count=2, base=2.0, max_backoff=60.0) == 4.0

def test_third_retry_delay():
    """retry_count=3, base=2 → 2^3 = 8.0s"""
    assert calculate_backoff(retry_count=3, base=2.0, max_backoff=60.0) == 8.0

def test_delay_grows_exponentially():
    """Each retry doubles the previous delay (base=2)."""
    delays = [calculate_backoff(i, base=2.0, max_backoff=9999.0) for i in range(1, 6)]
    # [2, 4, 8, 16, 32]
    for i in range(1, len(delays)):
        assert delays[i] == delays[i - 1] * 2.0


# Test the cap behaviour
def test_delay_capped_at_max_backoff():
    """2^6 = 64, which exceeds max_backoff=60 → should return 60.0"""
    assert calculate_backoff(retry_count=6, base=2.0, max_backoff=60.0) == 60.0

def test_delay_exactly_at_cap_is_not_exceeded():
    """2^5 = 32, max_backoff=32 → returns exactly 32.0 (not exceeded)"""
    assert calculate_backoff(retry_count=5, base=2.0, max_backoff=32.0) == 32.0

def test_delay_well_above_cap_is_clamped():
    """Very high retry_count should never exceed max_backoff."""
    assert calculate_backoff(retry_count=100, base=2.0, max_backoff=60.0) == 60.0


# Test different base values
def test_base_three():
    """retry_count=3, base=3 → 3^3 = 27.0s"""
    assert calculate_backoff(retry_count=3, base=3.0, max_backoff=60.0) == 27.0

def test_base_one_is_constant():
    """base=1 → 1^n = 1.0 always — no growth, useful for testing."""
    for i in range(1, 5):
        assert calculate_backoff(retry_count=i, base=1.0, max_backoff=60.0) == 1.0