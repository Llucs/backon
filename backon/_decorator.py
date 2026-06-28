import asyncio
import functools
import logging
import operator
import time as time_module
from collections.abc import Callable, Iterable
from typing import Any

from backon._common import (
    _config_handlers,
    _log_backoff,
    _log_giveup,
    _maybe_call,
    _prepare_logger,
    is_enabled,
)
from backon._conditions import (
    retry_if_exception_type,
    retry_if_result,
)
from backon._jitter import full_jitter
from backon._retry import _retry_async, _retry_sync
from backon._typing import (
    _CallableT,
    _Handler,
    _Jitterer,
    _MaybeCallable,
    _MaybeLogger,
    _MaybeSequence,
    _Predicate,
    _WaitGenerator,
)


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
    **wait_gen_kwargs: Any,
) -> Callable[[_CallableT], _CallableT]:
    def decorate(target):
        nonlocal logger, on_success, on_backoff, on_giveup, on_attempt, before_sleep

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

        condition = retry_if_result(predicate)

        if asyncio.iscoroutinefunction(target):
            _sleep = sleep or asyncio.sleep

            @functools.wraps(target)
            async def wrapper(*args, **kwargs):
                if not is_enabled():
                    return await target(*args, **kwargs)

                async def wrapped():
                    return await target(*args, **kwargs)

                return await _retry_async(
                    wrapped,
                    wait_gen,
                    condition=condition,
                    max_tries=_maybe_call(max_tries),
                    max_time=_maybe_call(max_time),
                    jitter=jitter,
                    on_success=on_success,
                    on_backoff=on_backoff,
                    on_giveup=on_giveup,
                    on_attempt=on_attempt,
                    before_sleep=before_sleep,
                    sleep=_sleep,
                    retry_error_callback=retry_error_callback,
                    raise_on_giveup=raise_on_giveup,
                    wait_gen_kwargs=wait_gen_kwargs,
                )

            return wrapper
        else:
            _sleep = sleep or time_module.sleep

            @functools.wraps(target)
            def wrapper(*args, **kwargs):
                if not is_enabled():
                    return target(*args, **kwargs)

                return _retry_sync(
                    lambda: target(*args, **kwargs),
                    wait_gen,
                    condition=condition,
                    max_tries=_maybe_call(max_tries),
                    max_time=_maybe_call(max_time),
                    jitter=jitter,
                    on_success=on_success,
                    on_backoff=on_backoff,
                    on_giveup=on_giveup,
                    on_attempt=on_attempt,
                    before_sleep=before_sleep,
                    sleep=_sleep,
                    retry_error_callback=retry_error_callback,
                    raise_on_giveup=raise_on_giveup,
                    wait_gen_kwargs=wait_gen_kwargs,
                )

            return wrapper

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
    **wait_gen_kwargs: Any,
) -> Callable[[_CallableT], _CallableT]:
    def decorate(target):
        nonlocal logger, on_success, on_backoff, on_giveup, on_attempt, before_sleep

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

        if isinstance(exception, type):
            exc_types = (exception,)
        else:
            exc_types = tuple(exception)

        condition = retry_if_exception_type(exc_types)
        if giveup is not None:

            def _condition(state):
                if not retry_if_exception_type(exc_types)(state):
                    return False
                if state.outcome and state.outcome.exception:
                    return not giveup(state.outcome.exception)
                return True

            condition = _condition

        if asyncio.iscoroutinefunction(target):
            _sleep = sleep or asyncio.sleep

            @functools.wraps(target)
            async def wrapper(*args, **kwargs):
                if not is_enabled():
                    return await target(*args, **kwargs)

                async def wrapped():
                    return await target(*args, **kwargs)

                return await _retry_async(
                    wrapped,
                    wait_gen,
                    condition=condition,
                    max_tries=_maybe_call(max_tries),
                    max_time=_maybe_call(max_time),
                    jitter=jitter,
                    on_success=on_success,
                    on_backoff=on_backoff,
                    on_giveup=on_giveup,
                    on_attempt=on_attempt,
                    before_sleep=before_sleep,
                    sleep=_sleep,
                    retry_error_callback=retry_error_callback,
                    raise_on_giveup=raise_on_giveup,
                    wait_gen_kwargs=wait_gen_kwargs,
                )

            return wrapper
        else:
            _sleep = sleep or time_module.sleep

            @functools.wraps(target)
            def wrapper(*args, **kwargs):
                if not is_enabled():
                    return target(*args, **kwargs)

                return _retry_sync(
                    lambda: target(*args, **kwargs),
                    wait_gen,
                    condition=condition,
                    max_tries=_maybe_call(max_tries),
                    max_time=_maybe_call(max_time),
                    jitter=jitter,
                    on_success=on_success,
                    on_backoff=on_backoff,
                    on_giveup=on_giveup,
                    on_attempt=on_attempt,
                    before_sleep=before_sleep,
                    sleep=_sleep,
                    retry_error_callback=retry_error_callback,
                    raise_on_giveup=raise_on_giveup,
                    wait_gen_kwargs=wait_gen_kwargs,
                )

            return wrapper

    return decorate
