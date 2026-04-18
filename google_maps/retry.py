"""Retry decorator with exponential backoff, jitter, and configurable exceptions."""

import asyncio
import functools
import logging
import random
from typing import Callable, Type

logger = logging.getLogger(__name__)


class RetryExhausted(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, func_name: str, attempts: int, last_error: Exception):
        self.func_name = func_name
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"{func_name} failed after {attempts} attempts: {last_error}"
        )


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable: tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
):
    """Async retry decorator with exponential backoff and jitter.

    Args:
        max_attempts: Total number of tries (1 = no retry).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Cap on the delay between retries.
        retryable: Tuple of exception types that trigger a retry.
        on_retry: Optional callback(attempt_number, exception) called before each retry sleep.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break

                    # Exponential backoff with full jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jittered = random.uniform(0, delay)

                    if on_retry:
                        on_retry(attempt, exc)
                    else:
                        logger.warning(
                            "%s attempt %d/%d failed (%s), retrying in %.1fs",
                            func.__name__,
                            attempt,
                            max_attempts,
                            exc,
                            jittered,
                        )

                    await asyncio.sleep(jittered)

            raise RetryExhausted(func.__name__, max_attempts, last_exc)

        return wrapper

    return decorator
