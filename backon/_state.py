from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class TryAgain(Exception):
    """Raise inside a retried function to force an immediate retry."""


class RetryError(Exception):
    """Raised when retry gives up. Wraps the last attempt's exception."""

    def __init__(self, last_attempt: Attempt) -> None:
        self.last_attempt = last_attempt
        cause = last_attempt.exception
        super().__init__(f"Retry failed after {last_attempt.tries} tries")
        if cause is not None:
            self.__cause__ = cause

    def reraise(self) -> None:
        cause = self.last_attempt.exception
        if cause is not None:
            raise cause from None


@dataclass
class Attempt:
    tries: int = 0
    exception: BaseException | None = None
    value: Any = None
    wait: float = 0.0
    elapsed: float = 0.0


@dataclass
class RetryState:
    target: Callable[..., Any] = lambda: None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    tries: int = 0
    start_time: float = 0.0
    elapsed: float = 0.0
    idle_for: float = 0.0
    outcome: Attempt | None = None
    _lock: threading.local = field(default_factory=threading.local)

    def __post_init__(self):
        self._lock.lock = threading.Lock()

    @property
    def statistics(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time,
            "attempt_number": self.tries,
            "idle_for": self.idle_for,
            "elapsed": self.elapsed,
        }

    def to_details(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "args": self.args,
            "kwargs": self.kwargs,
            "tries": self.tries,
            "elapsed": self.elapsed,
        }
