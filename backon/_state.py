from __future__ import annotations

import threading
import time as time_module
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class TryAgain(Exception):
    """Raise inside a retried function to force an immediate retry."""


class AttemptTimeoutError(Exception):
    """Raised when a single attempt exceeds the configured timeout."""


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
class AttemptResult:
    value: Any = None
    exception: BaseException | None = None


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


@dataclass
class RetryCallState:
    fn: Callable[..., Any] | None = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    attempt_number: int = 1
    outcome: Attempt | None = None
    outcome_timestamp: float | None = None
    start_time: float = 0.0
    idle_for: float = 0.0
    upcoming_sleep: float = 0.0

    @property
    def elapsed(self) -> float:
        if self.start_time == 0:
            return 0.0
        return time_module.monotonic() - self.start_time

    @property
    def seconds_since_start(self) -> float:
        return self.elapsed

    @property
    def statistics(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time,
            "attempt_number": self.attempt_number,
            "idle_for": self.idle_for,
            "elapsed": self.elapsed,
        }

    def to_details(self) -> dict[str, Any]:
        return {
            "target": self.fn,
            "args": self.args,
            "kwargs": self.kwargs,
            "tries": self.attempt_number,
            "elapsed": self.elapsed,
        }
