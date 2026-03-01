def calculate_backoff(retry_count: int, base: float = 2.0, max_backoff: float = 60.0) -> float:
    delay = base ** retry_count
    return min(delay, max_backoff)
