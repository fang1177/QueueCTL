"""
QueueCTL Exponential Backoff Calculator Module.

Calculates retry delay using backoff_base ^ attempts formulation.
"""


def calculate_backoff_delay(attempts: int, backoff_base: float = 2.0) -> float:
    """
    Calculates exponential backoff delay in seconds.

    Formula: delay = backoff_base ** attempts

    Example with base = 2.0:
        Attempt 1: 2.0 ^ 1 = 2 seconds
        Attempt 2: 2.0 ^ 2 = 4 seconds
        Attempt 3: 2.0 ^ 3 = 8 seconds
        Attempt 4: 2.0 ^ 4 = 16 seconds

    Args:
        attempts: Number of completed prior execution attempts.
        backoff_base: Base multiplier for backoff exponential.

    Returns:
        Delay in seconds before job becomes eligible for retry.
    """
    if attempts <= 0:
        return 0.0
    return float(backoff_base ** attempts)
