from __future__ import annotations

import logging
import operator
import threading
import time
from collections.abc import Awaitable, Callable, Iterable
from enum import Enum
from typing import Any, TypeVar, cast

from backon._conditions import RetryCondition, Stop
from backon._jitter import full_jitter
from backon._retry import Retrying
from backon._typing import (
    _Handler,
    _Jitterer,
    _MaybeCallable,
    _MaybeLogger,
    _MaybeSequence,
    _Predicate,
    _WaitGenerator,
)
from backon._wait_gen import expo

R = TypeVar("R")


class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        name: str = "",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._name = name
        self._lock = threading.Lock()
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0
        self._consecutive_successes = 0

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    @property
    def name(self) -> str:
        return self._name

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    @property
    def success_count(self) -> int:
        with self._lock:
            return self._consecutive_successes

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._consecutive_successes += 1
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._consecutive_successes = 0
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitBreakerState.OPEN

    def call(self, fn: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        current_state = self.state
        if current_state == CircuitBreakerState.OPEN:
            raise CircuitOpenError(self._name)
        if current_state == CircuitBreakerState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise CircuitOpenError(self._name)
                self._half_open_calls += 1
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            self.record_failure()
            raise
        self.record_success()
        return result

    async def async_call(
        self, fn: Callable[..., Awaitable[R]], *args: Any, **kwargs: Any
    ) -> R:
        current_state = self.state
        if current_state == CircuitBreakerState.OPEN:
            raise CircuitOpenError(self._name)
        if current_state == CircuitBreakerState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise CircuitOpenError(self._name)
                self._half_open_calls += 1
        try:
            result = await fn(*args, **kwargs)
        except BaseException:
            self.record_failure()
            raise
        self.record_success()
        return result

    def __call__(self, fn: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        return self.call(fn, *args, **kwargs)

    def __enter__(self) -> CircuitBreaker:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        pass

    async def __aenter__(self) -> CircuitBreaker:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        pass


class BreakerRetrying:
    def __init__(
        self,
        wait_gen: _WaitGenerator = expo,
        *,
        breaker: CircuitBreaker | None = None,
        predicate: _Predicate[Any] = operator.not_,
        exception: _MaybeSequence[type[Exception]] | None = None,
        max_tries: _MaybeCallable[int] | None = None,
        max_time: _MaybeCallable[float] | None = None,
        jitter: _Jitterer | None = full_jitter,
        giveup: _Predicate[Exception] = lambda e: False,
        condition: RetryCondition | None = None,
        stop: Stop | None = None,
        on_success: _Handler | Iterable[_Handler] | None = None,
        on_backoff: _Handler | Iterable[_Handler] | None = None,
        on_giveup: _Handler | Iterable[_Handler] | None = None,
        on_attempt: _Handler | Iterable[_Handler] | None = None,
        before_sleep: _Handler | Iterable[_Handler] | None = None,
        retry_error_callback: Callable[[dict], Any] | None = None,
        raise_on_giveup: bool = True,
        logger: _MaybeLogger = "backon",
        backoff_log_level: int = logging.INFO,
        giveup_log_level: int = logging.ERROR,
        sleep: Callable[[float], Any] | None = None,
        enabled: bool = True,
        name: str = "",
        **wait_gen_kwargs: Any,
    ) -> None:
        self._breaker = breaker or CircuitBreaker()
        self._retrying = Retrying(
            wait_gen,
            predicate=predicate,
            exception=exception,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            giveup=giveup,
            condition=condition,
            stop=stop,
            on_success=on_success,
            on_backoff=on_backoff,
            on_giveup=on_giveup,
            on_attempt=on_attempt,
            before_sleep=before_sleep,
            retry_error_callback=retry_error_callback,
            raise_on_giveup=raise_on_giveup,
            logger=logger,
            backoff_log_level=backoff_log_level,
            giveup_log_level=giveup_log_level,
            sleep=sleep,
            enabled=enabled,
            name=name,
            **wait_gen_kwargs,
        )

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    def call(self, target: Callable[..., R], *args: Any, **kwargs: Any) -> R:
        if self._breaker.state == CircuitBreakerState.OPEN:
            raise CircuitOpenError(self._breaker.name)
        try:
            result = self._retrying.call(target, *args, **kwargs)
        except BaseException:
            self._breaker.record_failure()
            raise
        self._breaker.record_success()
        return cast(R, result)

    async def async_call(
        self, target: Callable[..., R], *args: Any, **kwargs: Any
    ) -> R:
        if self._breaker.state == CircuitBreakerState.OPEN:
            raise CircuitOpenError(self._breaker.name)
        try:
            result = await self._retrying.async_call(target, *args, **kwargs)
        except BaseException:
            self._breaker.record_failure()
            raise
        self._breaker.record_success()
        return cast(R, result)
