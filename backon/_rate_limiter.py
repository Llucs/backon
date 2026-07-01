from __future__ import annotations

import threading
import time as time_module
from collections.abc import Callable
from typing import Any


class RateLimitError(Exception):
    pass


class RateLimiter:
    def __init__(self, max_calls: float, period: float = 1.0) -> None:
        self._max_calls = max_calls
        self._period = period
        self._lock = threading.Lock()
        self._timestamps: list[float] = []

    def acquire(self) -> bool:
        with self._lock:
            now = time_module.monotonic()
            cutoff = now - self._period
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self._max_calls:
                return False
            self._timestamps.append(now)
            return True

    def wait_time(self) -> float:
        with self._lock:
            if not self._timestamps:
                return 0.0
            now = time_module.monotonic()
            cutoff = now - self._period
            remaining = self._timestamps[0] - cutoff
            return max(0.0, remaining)

    def __call__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not self.acquire():
            raise RateLimitError(
                f"Rate limit of {self._max_calls} calls per {self._period}s"
                " exceeded"
            )
        return fn(*args, **kwargs)
