from __future__ import annotations

import asyncio
import inspect
import logging
import operator
import time as time_module
from collections.abc import Callable, Iterable
from typing import Any

from backon._common import (
    _apply_test_overrides,
    _config_handlers,
    _log_backoff,
    _log_giveup,
    _prepare_logger,
    is_enabled,
)
from backon._conditions import RetryCondition, Stop
from backon._jitter import full_jitter
from backon._rate_limiter import RateLimiter
from backon._retry._helpers import _make_default_condition, _make_default_stop
from backon._retry._loops import _retry_loop_async, _retry_loop_sync
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


def _retry_sync(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator,
    *,
    condition: RetryCondition | None = None,
    stop: Stop | None = None,
    predicate: _Predicate[Any] = operator.not_,
    exception: _MaybeSequence[type[Exception]] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
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
    wait_gen_kwargs: dict | None = None,
    before: _Handler | Iterable[_Handler] | None = None,
    after: _Handler | Iterable[_Handler] | None = None,
    _holder: dict | None = None,
    rate_limit: RateLimiter | None = None,
    attempt_timeout: float | None = None,
) -> Any:
    if wait_gen_kwargs is None:
        wait_gen_kwargs = {}
    if not is_enabled():
        return target()

    logger = _prepare_logger(logger)
    on_success = _config_handlers(on_success)
    on_backoff = _config_handlers(
        on_backoff,
        default_handler=_log_backoff,
        logger=logger,
        log_level=backoff_log_level,
    )
    on_giveup = _config_handlers(
        on_giveup,
        default_handler=_log_giveup,
        logger=logger,
        log_level=giveup_log_level,
    )
    on_attempt = _config_handlers(on_attempt)
    before_sleep = _config_handlers(before_sleep)
    before = _config_handlers(before)
    after = _config_handlers(after)

    max_tries, max_time = _apply_test_overrides(max_tries, max_time)

    if condition is None:
        condition = _make_default_condition(exception, giveup, predicate)
    if stop is None:
        stop = _make_default_stop(max_tries, max_time)

    _sleep = sleep or time_module.sleep

    return _retry_loop_sync(
        target,
        wait_gen,
        condition,
        stop,
        jitter,
        on_success,
        on_backoff,
        on_giveup,
        on_attempt,
        before_sleep,
        _sleep,
        retry_error_callback,
        raise_on_giveup,
        max_time,
        wait_gen_kwargs,
        before=before,
        after=after,
        _holder=_holder,
        rate_limit=rate_limit,
        attempt_timeout=attempt_timeout,
    )


async def _retry_async(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator,
    *,
    condition: RetryCondition | None = None,
    stop: Stop | None = None,
    predicate: _Predicate[Any] = operator.not_,
    exception: _MaybeSequence[type[Exception]] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
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
    wait_gen_kwargs: dict | None = None,
    before: _Handler | Iterable[_Handler] | None = None,
    after: _Handler | Iterable[_Handler] | None = None,
    _holder: dict | None = None,
    rate_limit: RateLimiter | None = None,
    attempt_timeout: float | None = None,
) -> Any:
    if wait_gen_kwargs is None:
        wait_gen_kwargs = {}
    if not is_enabled():
        return await target()

    logger = _prepare_logger(logger)
    on_success = _config_handlers(on_success)
    on_backoff = _config_handlers(
        on_backoff,
        default_handler=_log_backoff,
        logger=logger,
        log_level=backoff_log_level,
    )
    on_giveup = _config_handlers(
        on_giveup,
        default_handler=_log_giveup,
        logger=logger,
        log_level=giveup_log_level,
    )
    on_attempt = _config_handlers(on_attempt)
    before_sleep = _config_handlers(before_sleep)
    before = _config_handlers(before)
    after = _config_handlers(after)

    max_tries, max_time = _apply_test_overrides(max_tries, max_time)

    if condition is None:
        condition = _make_default_condition(exception, giveup, predicate)
    if stop is None:
        stop = _make_default_stop(max_tries, max_time)

    _sleep = sleep or asyncio.sleep

    return await _retry_loop_async(
        target,
        wait_gen,
        condition,
        stop,
        jitter,
        on_success,
        on_backoff,
        on_giveup,
        on_attempt,
        before_sleep,
        _sleep,
        retry_error_callback,
        raise_on_giveup,
        max_time,
        wait_gen_kwargs,
        before=before,
        after=after,
        _holder=_holder,
        rate_limit=rate_limit,
        attempt_timeout=attempt_timeout,
    )


def retry(
    target: Callable[..., Any],
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
    name: str = "",
    before: _Handler | Iterable[_Handler] | None = None,
    after: _Handler | Iterable[_Handler] | None = None,
    rate_limit: RateLimiter | None = None,
    attempt_timeout: float | None = None,
    **wait_gen_kwargs: Any,
) -> Any:
    if inspect.iscoroutinefunction(target):
        return _retry_async(
            target,
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
            wait_gen_kwargs=wait_gen_kwargs,
            before=before,
            after=after,
            rate_limit=rate_limit,
            attempt_timeout=attempt_timeout,
        )
    return _retry_sync(
        target,
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
        wait_gen_kwargs=wait_gen_kwargs,
        before=before,
        after=after,
        rate_limit=rate_limit,
        attempt_timeout=attempt_timeout,
    )
