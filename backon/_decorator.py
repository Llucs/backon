from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import operator
import time as time_module
from collections.abc import Callable, Iterable
from typing import Any, cast

from backon._common import (
    _config_handlers,
    _log_backoff,
    _log_giveup,
    _maybe_call,
    _prepare_logger,
    is_enabled,
)
from backon._conditions import (
    RetryCondition,
    retry_if_exception_type,
    retry_if_result,
)
from backon._jitter import full_jitter
from backon._rate_limiter import RateLimiter
from backon._retry import _retry_async_inner, _retry_sync_inner
from backon._state import RetryState
from backon._typing import (
    P,
    R,
    _Handler,
    _Jitterer,
    _MaybeCallable,
    _MaybeLogger,
    _MaybeSequence,
    _Predicate,
    _WaitGenerator,
)


def _prepare_handlers(
    logger: _MaybeLogger,
    on_success: _Handler | Iterable[_Handler] | None,
    on_backoff: _Handler | Iterable[_Handler] | None,
    on_giveup: _Handler | Iterable[_Handler] | None,
    on_attempt: _Handler | Iterable[_Handler] | None,
    before_sleep: _Handler | Iterable[_Handler] | None,
    before: _Handler | Iterable[_Handler] | None,
    after: _Handler | Iterable[_Handler] | None,
    backoff_log_level: int,
    giveup_log_level: int,
) -> tuple:
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
    return (
        logger,
        on_success,
        on_backoff,
        on_giveup,
        on_attempt,
        before_sleep,
        before,
        after,
    )


def _build_retry_kw(
    condition: RetryCondition,
    max_tries: _MaybeCallable[int] | None,
    max_time: _MaybeCallable[float] | None,
    jitter: _Jitterer | None,
    on_success: Any,
    on_backoff: Any,
    on_giveup: Any,
    on_attempt: Any,
    before_sleep: Any,
    retry_error_callback: Callable[[dict], Any] | None,
    raise_on_giveup: bool,
    wait_gen_kwargs: dict[str, Any],
    before: Any,
    after: Any,
    rate_limit: RateLimiter | None,
    attempt_timeout: float | None,
) -> dict[str, Any]:
    return {
        "condition": condition,
        "max_tries": _maybe_call(max_tries),
        "max_time": _maybe_call(max_time),
        "jitter": jitter,
        "on_success": on_success,
        "on_backoff": on_backoff,
        "on_giveup": on_giveup,
        "on_attempt": on_attempt,
        "before_sleep": before_sleep,
        "retry_error_callback": retry_error_callback,
        "raise_on_giveup": raise_on_giveup,
        "wait_gen_kwargs": wait_gen_kwargs,
        "before": before,
        "after": after,
        "rate_limit": rate_limit,
        "attempt_timeout": attempt_timeout,
    }


def _make_retry_with(
    target: Callable[P, R],
    wait_gen: _WaitGenerator,
    *,
    predicate: _Predicate[Any] | None = None,
    exception: _MaybeSequence[type[Exception]] | None = None,
    giveup: _Predicate[Exception] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = None,
    on_success: _Handler | Iterable[_Handler] | None = None,
    on_backoff: _Handler | Iterable[_Handler] | None = None,
    on_giveup: _Handler | Iterable[_Handler] | None = None,
    on_attempt: _Handler | Iterable[_Handler] | None = None,
    before_sleep: _Handler | Iterable[_Handler] | None = None,
    logger: _MaybeLogger = None,
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    retry_error_callback: Callable[[dict], Any] | None = None,
    raise_on_giveup: bool = True,
    sleep: Callable[[float], Any] | None = None,
    before: _Handler | Iterable[_Handler] | None = None,
    after: _Handler | Iterable[_Handler] | None = None,
    rate_limit: RateLimiter | None = None,
    attempt_timeout: float | None = None,
    wait_gen_kwargs: dict[str, Any] | None = None,
) -> Callable[..., Callable[P, R]]:
    is_predicate = predicate is not None
    known = {
        "max_tries",
        "max_time",
        "jitter",
        "on_success",
        "on_backoff",
        "on_giveup",
        "on_attempt",
        "before_sleep",
        "logger",
        "backoff_log_level",
        "giveup_log_level",
        "retry_error_callback",
        "raise_on_giveup",
        "sleep",
        "before",
        "after",
        "rate_limit",
        "attempt_timeout",
        "wait_gen",
    }
    if is_predicate:
        known.add("predicate")
    else:
        known.update({"giveup", "exception"})

    extra_name = "predicate" if is_predicate else "exception"
    extra_value: Any = predicate if is_predicate else exception
    factory = on_predicate if is_predicate else on_exception

    def retry_with(**overrides: Any) -> Callable[P, R]:
        kw: dict[str, Any] = {
            "max_tries": max_tries,
            "max_time": max_time,
            "jitter": jitter,
            "on_success": on_success,
            "on_backoff": on_backoff,
            "on_giveup": on_giveup,
            "on_attempt": on_attempt,
            "before_sleep": before_sleep,
            "logger": logger,
            "backoff_log_level": backoff_log_level,
            "giveup_log_level": giveup_log_level,
            "retry_error_callback": retry_error_callback,
            "raise_on_giveup": raise_on_giveup,
            "sleep": sleep,
            "before": before,
            "after": after,
            "rate_limit": rate_limit,
            "attempt_timeout": attempt_timeout,
        }
        if not is_predicate:
            kw["giveup"] = giveup

        kw.update(overrides)

        _wg = kw.pop("wait_gen", wait_gen)
        _extra = kw.pop(extra_name, extra_value)

        _wk = dict(wait_gen_kwargs or {})
        for k in list(kw):
            if k not in known:
                _wk[k] = kw.pop(k)

        return factory(_wg, _extra, **kw, **_wk)(target)

    return retry_with


def on_predicate(
    wait_gen: _WaitGenerator,
    predicate: _Predicate[Any] = operator.not_,
    *,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    on_success: _Handler | Iterable[_Handler] | None = None,
    on_backoff: _Handler | Iterable[_Handler] | None = None,
    on_giveup: _Handler | Iterable[_Handler] | None = None,
    on_attempt: _Handler | Iterable[_Handler] | None = None,
    before_sleep: _Handler | Iterable[_Handler] | None = None,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    retry_error_callback: Callable[[dict], Any] | None = None,
    raise_on_giveup: bool = True,
    sleep: Callable[[float], Any] | None = None,
    before: _Handler | Iterable[_Handler] | None = None,
    after: _Handler | Iterable[_Handler] | None = None,
    rate_limit: RateLimiter | None = None,
    attempt_timeout: float | None = None,
    **wait_gen_kwargs: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(target: Callable[P, R]) -> Callable[P, R]:
        nonlocal logger, on_success, on_backoff, on_giveup, on_attempt, before_sleep
        nonlocal before, after

        (
            _r_logger,
            _r_on_success,
            _r_on_backoff,
            _r_on_giveup,
            _r_on_attempt,
            _r_before_sleep,
            _r_before,
            _r_after,
        ) = (
            logger,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            before,
            after,
        )

        (
            logger,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            before,
            after,
        ) = _prepare_handlers(
            logger,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            before,
            after,
            backoff_log_level,
            giveup_log_level,
        )

        condition: RetryCondition = retry_if_result(predicate)

        _kw = _build_retry_kw(
            condition,
            max_tries,
            max_time,
            jitter,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            retry_error_callback,
            raise_on_giveup,
            wait_gen_kwargs,
            before,
            after,
            rate_limit,
            attempt_timeout,
        )

        _retry_with = _make_retry_with(
            target,
            wait_gen,
            predicate=predicate,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            on_success=_r_on_success,
            on_backoff=_r_on_backoff,
            on_giveup=_r_on_giveup,
            on_attempt=_r_on_attempt,
            before_sleep=_r_before_sleep,
            logger=_r_logger,
            backoff_log_level=backoff_log_level,
            giveup_log_level=giveup_log_level,
            retry_error_callback=retry_error_callback,
            raise_on_giveup=raise_on_giveup,
            sleep=sleep,
            before=_r_before,
            after=_r_after,
            rate_limit=rate_limit,
            attempt_timeout=attempt_timeout,
            wait_gen_kwargs=wait_gen_kwargs,
        )

        if inspect.isasyncgenfunction(target):
            _sleep = sleep or asyncio.sleep

            async def _collect_async_gen(agen):
                result = []
                async for item in agen:
                    result.append(item)
                return result

            @functools.wraps(target)
            async def wrapper(*args: P.args, **kwargs: P.kwargs):
                if not is_enabled():
                    async for item in target(*args, **kwargs):
                        yield item
                    return

                collected = await _retry_async_inner(
                    lambda: _collect_async_gen(target(*args, **kwargs)),
                    wait_gen,
                    sleep=_sleep,
                    **_kw,
                )
                if collected is not None:
                    for item in collected:
                        yield item

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)

        if inspect.isgeneratorfunction(target):
            _sleep = sleep or time_module.sleep

            @functools.wraps(target)
            def wrapper(*args: P.args, **kwargs: P.kwargs):
                if not is_enabled():
                    yield from target(*args, **kwargs)
                    return

                collected = _retry_sync_inner(
                    lambda: list(target(*args, **kwargs)),
                    wait_gen,
                    sleep=_sleep,
                    **_kw,
                )
                if collected is not None:
                    yield from collected

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)

        if inspect.iscoroutinefunction(target):
            _sleep = sleep or asyncio.sleep

            @functools.wraps(target)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if not is_enabled():
                    return cast(R, await target(*args, **kwargs))

                async def wrapped():
                    return await target(*args, **kwargs)

                return cast(
                    R,
                    await _retry_async_inner(
                        wrapped,
                        wait_gen,
                        sleep=_sleep,
                        **_kw,
                    ),
                )

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)
        else:
            _sleep = sleep or time_module.sleep

            @functools.wraps(target)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if not is_enabled():
                    return cast(R, target(*args, **kwargs))

                return cast(
                    R,
                    _retry_sync_inner(
                        lambda: target(*args, **kwargs),
                        wait_gen,
                        sleep=_sleep,
                        **_kw,
                    ),
                )

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)

    return decorate


def on_exception(
    wait_gen: _WaitGenerator,
    exception: _MaybeSequence[type[Exception]],
    *,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
    on_success: _Handler | Iterable[_Handler] | None = None,
    on_backoff: _Handler | Iterable[_Handler] | None = None,
    on_giveup: _Handler | Iterable[_Handler] | None = None,
    on_attempt: _Handler | Iterable[_Handler] | None = None,
    before_sleep: _Handler | Iterable[_Handler] | None = None,
    raise_on_giveup: bool = True,
    retry_error_callback: Callable[[dict], Any] | None = None,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Callable[[float], Any] | None = None,
    before: _Handler | Iterable[_Handler] | None = None,
    after: _Handler | Iterable[_Handler] | None = None,
    rate_limit: RateLimiter | None = None,
    attempt_timeout: float | None = None,
    **wait_gen_kwargs: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(target: Callable[P, R]) -> Callable[P, R]:
        nonlocal logger, on_success, on_backoff, on_giveup, on_attempt, before_sleep
        nonlocal before, after

        (
            _r_logger,
            _r_on_success,
            _r_on_backoff,
            _r_on_giveup,
            _r_on_attempt,
            _r_before_sleep,
            _r_before,
            _r_after,
        ) = (
            logger,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            before,
            after,
        )

        (
            logger,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            before,
            after,
        ) = _prepare_handlers(
            logger,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            before,
            after,
            backoff_log_level,
            giveup_log_level,
        )

        exc_types: tuple[type[Exception], ...]
        exc_types = (exception,) if isinstance(exception, type) else tuple(exception)

        condition: RetryCondition = retry_if_exception_type(exc_types)
        if giveup is not None:

            def _condition(state: RetryState) -> bool | float:
                if not retry_if_exception_type(exc_types)(state):
                    return False
                if state.outcome and isinstance(state.outcome.exception, Exception):
                    result = giveup(state.outcome.exception)
                    if isinstance(result, bool):
                        return not result
                    if isinstance(result, (int, float)):
                        return float(result)
                    return True
                return True

            condition = cast(RetryCondition, _condition)

        _kw = _build_retry_kw(
            condition,
            max_tries,
            max_time,
            jitter,
            on_success,
            on_backoff,
            on_giveup,
            on_attempt,
            before_sleep,
            retry_error_callback,
            raise_on_giveup,
            wait_gen_kwargs,
            before,
            after,
            rate_limit,
            attempt_timeout,
        )

        _retry_with = _make_retry_with(
            target,
            wait_gen,
            exception=exception,
            giveup=giveup,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            on_success=_r_on_success,
            on_backoff=_r_on_backoff,
            on_giveup=_r_on_giveup,
            on_attempt=_r_on_attempt,
            before_sleep=_r_before_sleep,
            logger=_r_logger,
            backoff_log_level=backoff_log_level,
            giveup_log_level=giveup_log_level,
            retry_error_callback=retry_error_callback,
            raise_on_giveup=raise_on_giveup,
            sleep=sleep,
            before=_r_before,
            after=_r_after,
            rate_limit=rate_limit,
            attempt_timeout=attempt_timeout,
            wait_gen_kwargs=wait_gen_kwargs,
        )

        if inspect.isasyncgenfunction(target):
            _sleep = sleep or asyncio.sleep

            async def _collect_async_gen(agen):
                result = []
                async for item in agen:
                    result.append(item)
                return result

            @functools.wraps(target)
            async def wrapper(*args: P.args, **kwargs: P.kwargs):
                if not is_enabled():
                    async for item in target(*args, **kwargs):
                        yield item
                    return

                collected = await _retry_async_inner(
                    lambda: _collect_async_gen(target(*args, **kwargs)),
                    wait_gen,
                    sleep=_sleep,
                    **_kw,
                )
                if collected is not None:
                    for item in collected:
                        yield item

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)

        if inspect.isgeneratorfunction(target):
            _sleep = sleep or time_module.sleep

            @functools.wraps(target)
            def wrapper(*args: P.args, **kwargs: P.kwargs):
                if not is_enabled():
                    yield from target(*args, **kwargs)
                    return

                collected = _retry_sync_inner(
                    lambda: list(target(*args, **kwargs)),
                    wait_gen,
                    sleep=_sleep,
                    **_kw,
                )
                if collected is not None:
                    yield from collected

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)

        if inspect.iscoroutinefunction(target):
            _sleep = sleep or asyncio.sleep

            @functools.wraps(target)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if not is_enabled():
                    return cast(R, await target(*args, **kwargs))

                async def wrapped():
                    return await target(*args, **kwargs)

                return cast(
                    R,
                    await _retry_async_inner(
                        wrapped,
                        wait_gen,
                        sleep=_sleep,
                        **_kw,
                    ),
                )

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)
        else:
            _sleep = sleep or time_module.sleep

            @functools.wraps(target)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if not is_enabled():
                    return cast(R, target(*args, **kwargs))

                return cast(
                    R,
                    _retry_sync_inner(
                        lambda: target(*args, **kwargs),
                        wait_gen,
                        sleep=_sleep,
                        **_kw,
                    ),
                )

            wrapper.retry_with = _retry_with  # type: ignore[attr-defined]
            return cast(Callable[P, R], wrapper)

    return decorate
