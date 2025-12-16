"""Thread-safe rate limiter for API requests.

This module provides a rate limiter to control the frequency of API calls,
preventing rate limit errors when making parallel requests.

Usage:
    rate_limiter = RateLimiter(max_requests_per_second=2.0)

    # In each worker thread:
    rate_limiter.acquire()  # Will block if rate limit exceeded
    make_api_call()
"""

import threading
import time
from dataclasses import dataclass

from loguru import logger


@dataclass
class RateLimiterStats:
    """Statistics for rate limiter usage.

    Attributes:
        total_requests: Total number of requests processed
        total_waits: Number of times we had to wait for rate limit
        total_wait_time: Total time spent waiting (seconds)
    """

    total_requests: int = 0
    total_waits: int = 0
    total_wait_time: float = 0.0


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm.

    This rate limiter ensures that API requests don't exceed a specified
    rate per second, even when called from multiple threads concurrently.

    Attributes:
        max_requests_per_second: Maximum allowed requests per second

    Example:
        >>> limiter = RateLimiter(max_requests_per_second=2.0)
        >>> for i in range(10):
        ...     limiter.acquire()
        ...     print(f"Request {i} at {time.time()}")
    """

    def __init__(self, max_requests_per_second: float = 2.0) -> None:
        """Initialize rate limiter.

        Args:
            max_requests_per_second: Maximum requests allowed per second.
                Default is 2.0, which means at most 2 requests per second.
        """
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = (
            1.0 / max_requests_per_second
        )  # Minimum time between requests

        # Thread synchronization
        self._lock = threading.Lock()
        self._request_times: list[float] = []

        # Statistics
        self._stats = RateLimiterStats()

        logger.debug(
            f"RateLimiter initialized: max {max_requests_per_second} req/s, "
            f"min interval {self.min_interval:.3f}s"
        )

    def acquire(self) -> float:
        """Acquire permission to make a request.

        This method will block if the rate limit would be exceeded,
        waiting until it's safe to proceed.

        Returns:
            float: The actual wait time in seconds (0 if no wait needed)
        """
        with self._lock:
            now = time.time()
            wait_time = 0.0

            # Clean up old request times (older than 1 second)
            cutoff = now - 1.0
            self._request_times = [t for t in self._request_times if t > cutoff]

            # Check if we need to wait
            if len(self._request_times) >= self.max_requests_per_second:
                # Calculate how long to wait
                oldest_in_window = self._request_times[0]
                wait_time = 1.0 - (now - oldest_in_window)

                if wait_time > 0:
                    self._stats.total_waits += 1
                    self._stats.total_wait_time += wait_time

                    logger.debug(
                        f"Rate limit reached, waiting {wait_time:.3f}s "
                        f"(current: {len(self._request_times)} requests in window)"
                    )

                    # Release lock while sleeping to allow other operations
                    self._lock.release()
                    try:
                        time.sleep(wait_time)
                    finally:
                        self._lock.acquire()

                    # Update now after sleeping
                    now = time.time()
                    # Clean up again after sleep
                    cutoff = now - 1.0
                    self._request_times = [t for t in self._request_times if t > cutoff]

            # Record this request
            self._request_times.append(now)
            self._stats.total_requests += 1

            return wait_time

    def get_stats(self) -> RateLimiterStats:
        """Get rate limiter statistics.

        Returns:
            RateLimiterStats: Current statistics
        """
        with self._lock:
            return RateLimiterStats(
                total_requests=self._stats.total_requests,
                total_waits=self._stats.total_waits,
                total_wait_time=self._stats.total_wait_time,
            )

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        with self._lock:
            self._stats = RateLimiterStats()

    @property
    def current_rate(self) -> float:
        """Get current request rate (requests in last second).

        Returns:
            float: Number of requests in the last second
        """
        with self._lock:
            now = time.time()
            cutoff = now - 1.0
            return sum(1 for t in self._request_times if t > cutoff)


class NoOpRateLimiter(RateLimiter):
    """A no-operation rate limiter that doesn't limit anything.

    Useful for testing or when rate limiting is disabled.
    """

    def __init__(self) -> None:
        """Initialize no-op rate limiter."""
        super().__init__(max_requests_per_second=float("inf"))

    def acquire(self) -> float:
        """Always returns immediately without waiting.

        Returns:
            float: Always 0.0 (no wait)
        """
        with self._lock:
            self._stats.total_requests += 1
        return 0.0
