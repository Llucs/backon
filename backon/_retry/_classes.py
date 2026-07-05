from __future__ import annotations

import inspect
import logging
import operator
import time as time_module
from collections.abc import Callable, Iterable
from typing import Any

from backon._common import _elapsed, _init_wait_gen, _maybe_call, _now
from backon._conditions import RetryCondition, Stop
from backon._jitter import full_jitter
from backon._rate_limiter import RateLimiter
from backon._retry._api import _retry_async, _retry_sync
from backon._retry._helpers import _make_default_condition, _make_default_stop
from backon._state import Attempt, RetryCallState, RetryState
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


class _RetryAttempt:
    def __init__(self):
        self._exception: BaseException | None = None
        self._value: Any = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._exception = exc_val
            return True
        return False

    def set_value(self, value: Any) -> None:
        self._value = value

    @property
    def failed(self) -> bool:
        return self._exception is not None

    @property
    def exception(self) -> BaseException | None:
        return self._exception

    @property
    def value(self) -> Any:
        return self._value


class Retrying:
    def __init__(
        self,
        wait_gen: _WaitGenerator = expo,
        *,
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
        before: _Handler | Iterable[_Handler] | None = None,
        after: _Handler | Iterable[_Handler] | None = None,
        rate_limit: RateLimiter | None = None,
        attempt_timeout: float | None = None,
        **wait_gen_kwargs: Any,
    ):
        self._wait_gen = wait_gen
        self._predicate = predicate
        self._exception = exception
        self._max_tries = max_tries
        self._max_time = max_time
        self._jitter = jitter
        self._giveup = giveup
        self._condition = condition
        self._stop = stop
        self._on_success = on_success
        self._on_backoff = on_backoff
        self._on_giveup = on_giveup
        self._on_attempt = on_attempt
        self._before_sleep = before_sleep
        self._retry_error_callback = retry_error_callback
        self._raise_on_giveup = raise_on_giveup
        self._logger = logger
        self._backoff_log_level = backoff_log_level
        self._giveup_log_level = giveup_log_level
        self._sleep = sleep
        self._enabled = enabled
        self._name = name
        self._before = before
        self._after = after
        self._wait_gen_kwargs = wait_gen_kwargs
        self._rate_limit = rate_limit
        self._attempt_timeout = attempt_timeout
        self._state: RetryState | None = None
        self._call_state: RetryCallState | None = None

    @property
    def statistics(self) -> dict:
        if self._call_state is not None:
            return self._call_state.statistics
        if self._state is not None:
            return self._state.statistics
        return {}

    @property
    def call_state(self) -> RetryCallState | None:
        return self._call_state

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        pass

    def __iter__(self):
        self._iter_state = RetryState(target=self._name or "Retrying")
        self._iter_state.start_time = _now()
        self._iter_state.tries = 0
        self._last_attempt: _RetryAttempt | None = None
        max_tries = _maybe_call(self._max_tries)
        max_time = _maybe_call(self._max_time)
        self._iter_wait = _init_wait_gen(self._wait_gen, self._wait_gen_kwargs)
        self._iter_stop = self._stop or _make_default_stop(max_tries, max_time)
        self._iter_condition = self._condition or _make_default_condition(
            self._exception, self._giveup, self._predicate
        )
        return self

    def __next__(self) -> _RetryAttempt:
        if self._last_attempt is not None:
            if not self._last_attempt.failed:
                raise StopIteration

            exc = self._last_attempt._exception
            assert exc is not None
            outcome = Attempt(
                tries=self._iter_state.tries,
                elapsed=self._iter_state.elapsed,
                exception=exc,
            )
            self._iter_state.outcome = outcome

            if not self._iter_condition(self._iter_state):
                if self._raise_on_giveup:
                    raise exc
                raise StopIteration

            if self._iter_stop(self._iter_state):
                if self._raise_on_giveup:
                    raise exc
                raise StopIteration

            max_time = _maybe_call(self._max_time)
            try:
                value = self._iter_wait.send(exc)
                if self._jitter is not None:
                    seconds = self._jitter(value)
                else:
                    seconds = value
                if max_time is not None:
                    seconds = min(seconds, max_time - self._iter_state.elapsed)
            except StopIteration:
                if self._raise_on_giveup:
                    raise exc from None
                raise StopIteration from None

            sleep_fn = self._sleep or time_module.sleep
            if seconds > 0:
                sleep_fn(seconds)

        self._iter_state.tries += 1
        self._iter_state.elapsed = _elapsed(self._iter_state.start_time)

        attempt = _RetryAttempt()
        self._last_attempt = attempt
        return attempt

    def copy(self) -> Retrying:
        return Retrying(
            self._wait_gen,
            predicate=self._predicate,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            giveup=self._giveup,
            condition=self._condition,
            stop=self._stop,
            on_success=self._on_success,
            on_backoff=self._on_backoff,
            on_giveup=self._on_giveup,
            on_attempt=self._on_attempt,
            before_sleep=self._before_sleep,
            retry_error_callback=self._retry_error_callback,
            raise_on_giveup=self._raise_on_giveup,
            logger=self._logger,
            backoff_log_level=self._backoff_log_level,
            giveup_log_level=self._giveup_log_level,
            sleep=self._sleep,
            enabled=self._enabled,
            name=self._name,
            before=self._before,
            after=self._after,
            rate_limit=self._rate_limit,
            attempt_timeout=self._attempt_timeout,
            **self._wait_gen_kwargs,
        )

    def call(self, target: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(target):
            raise TypeError(
                "Use await with Retrying.call() for async functions, "
                "or pass a sync function"
            )

        def wrapped():
            return target(*args, **kwargs)

        _holder: dict = {}
        try:
            result = _retry_sync(
                wrapped,
                self._wait_gen,
                predicate=self._predicate,
                exception=self._exception,
                max_tries=self._max_tries,
                max_time=self._max_time,
                jitter=self._jitter,
                giveup=self._giveup,
                condition=self._condition,
                stop=self._stop,
                on_success=self._on_success,
                on_backoff=self._on_backoff,
                on_giveup=self._on_giveup,
                on_attempt=self._on_attempt,
                before_sleep=self._before_sleep,
                retry_error_callback=self._retry_error_callback,
                raise_on_giveup=self._raise_on_giveup,
                logger=self._logger,
                backoff_log_level=self._backoff_log_level,
                giveup_log_level=self._giveup_log_level,
                sleep=self._sleep,
                wait_gen_kwargs=self._wait_gen_kwargs,
                before=self._before,
                after=self._after,
                _holder=_holder,
                rate_limit=self._rate_limit,
                attempt_timeout=self._attempt_timeout,
            )
            return result
        finally:
            self._state = _holder.get("state")
            self._call_state = _holder.get("call_state")

    async def async_call(
        self, target: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        async def wrapped():
            return await target(*args, **kwargs)

        _holder: dict = {}
        try:
            result = await _retry_async(
                wrapped,
                self._wait_gen,
                predicate=self._predicate,
                exception=self._exception,
                max_tries=self._max_tries,
                max_time=self._max_time,
                jitter=self._jitter,
                giveup=self._giveup,
                condition=self._condition,
                stop=self._stop,
                on_success=self._on_success,
                on_backoff=self._on_backoff,
                on_giveup=self._on_giveup,
                on_attempt=self._on_attempt,
                before_sleep=self._before_sleep,
                retry_error_callback=self._retry_error_callback,
                raise_on_giveup=self._raise_on_giveup,
                logger=self._logger,
                backoff_log_level=self._backoff_log_level,
                giveup_log_level=self._giveup_log_level,
                sleep=self._sleep,
                wait_gen_kwargs=self._wait_gen_kwargs,
                before=self._before,
                after=self._after,
                _holder=_holder,
                rate_limit=self._rate_limit,
                attempt_timeout=self._attempt_timeout,
            )
            return result
        finally:
            self._state = _holder.get("state")
            self._call_state = _holder.get("call_state")


def sleep_using_event(event) -> Callable[[float], None]:
    """Return a sleep function that blocks on an event's wait timeout."""

    def sleep(seconds: float) -> None:
        event.wait(timeout=seconds)

    return sleep


class RetryingCaller:
    def __init__(
        self,
        wait_gen: _WaitGenerator = expo,
        *,
        exception: type[Exception] | None = None,
        max_tries: int | None = None,
        max_time: float | None = None,
        jitter: _Jitterer | None = full_jitter,
        rate_limit: RateLimiter | None = None,
        attempt_timeout: float | None = None,
        **wait_gen_kwargs: Any,
    ) -> None:
        self._wait_gen = wait_gen
        self._exception = exception
        self._max_tries = max_tries
        self._max_time = max_time
        self._jitter = jitter
        self._rate_limit = rate_limit
        self._attempt_timeout = attempt_timeout
        self._wait_gen_kwargs = wait_gen_kwargs

    def on(self, exception: type[Exception]) -> RetryingCaller:
        new = self.copy()
        new._exception = exception
        return new

    def __call__(self, target: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(target):
            raise TypeError(
                "Use AsyncRetryingCaller for async functions, or pass a sync function"
            )
        return _retry_sync(
            lambda: target(*args, **kwargs),
            self._wait_gen,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            wait_gen_kwargs=self._wait_gen_kwargs or None,
            rate_limit=self._rate_limit,
            attempt_timeout=self._attempt_timeout,
        )

    def copy(self) -> RetryingCaller:
        return RetryingCaller(
            self._wait_gen,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            rate_limit=self._rate_limit,
            attempt_timeout=self._attempt_timeout,
            **self._wait_gen_kwargs,
        )


class AsyncRetryingCaller:
    def __init__(
        self,
        wait_gen: _WaitGenerator = expo,
        *,
        exception: type[Exception] | None = None,
        max_tries: int | None = None,
        max_time: float | None = None,
        jitter: _Jitterer | None = full_jitter,
        rate_limit: RateLimiter | None = None,
        attempt_timeout: float | None = None,
        **wait_gen_kwargs: Any,
    ) -> None:
        self._wait_gen = wait_gen
        self._exception = exception
        self._max_tries = max_tries
        self._max_time = max_time
        self._jitter = jitter
        self._rate_limit = rate_limit
        self._attempt_timeout = attempt_timeout
        self._wait_gen_kwargs = wait_gen_kwargs

    def on(self, exception: type[Exception]) -> AsyncRetryingCaller:
        new = self.copy()
        new._exception = exception
        return new

    async def __call__(
        self, target: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        async def wrapped():
            return await target(*args, **kwargs)

        return await _retry_async(
            wrapped,
            self._wait_gen,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            wait_gen_kwargs=self._wait_gen_kwargs or None,
            rate_limit=self._rate_limit,
            attempt_timeout=self._attempt_timeout,
        )

    def copy(self) -> AsyncRetryingCaller:
        return AsyncRetryingCaller(
            self._wait_gen,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            rate_limit=self._rate_limit,
            attempt_timeout=self._attempt_timeout,
            **self._wait_gen_kwargs,
        )
