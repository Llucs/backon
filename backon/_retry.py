from __future__ import annotations

import asyncio
import inspect
import logging
import operator
import time as time_module
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FuturesTimeoutError
from datetime import timedelta
from typing import Any

from backon._common import (
    _check_hot_loop,
    _config_handlers,
    _elapsed,
    _init_wait_gen,
    _is_custom_wait,
    _log_backoff,
    _log_giveup,
    _maybe_call,
    _next_wait,
    _now,
    _prepare_logger,
    is_enabled,
)
from backon._conditions import (
    RetryCondition,
    Stop,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    stop_any,
    stop_never,
)
from backon._context import _retry_context_manager
from backon._jitter import full_jitter
from backon._rate_limiter import RateLimiter
from backon._state import (
    Attempt,
    AttemptTimeoutError,
    RetryCallState,
    RetryState,
    TryAgain,
)
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


def _call_hdlrs(hdlrs, details):
    if hdlrs:
        for h in hdlrs:
            h(details)


async def _call_hdlrs_async(handlers, details):
    if handlers:
        for handler in handlers:
            if inspect.iscoroutinefunction(handler):
                await handler(details)
            else:
                handler(details)


def _to_seconds(value: float | int | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _make_default_stop(max_tries, max_time):
    stops = []
    if max_tries is not None:
        stops.append(stop_after_attempt(max_tries))
    if max_time is not None:
        stops.append(stop_after_delay(_to_seconds(max_time)))
    if not stops:
        return stop_never()
    return stop_any(*stops)


def _make_default_condition(exception, giveup, predicate):
    if exception is not None:
        if isinstance(exception, type):
            exc_types = (exception,)
        else:
            exc_types = tuple(exception)

        condition = retry_if_exception_type(exc_types)

        if giveup is not None:

            def wrapped(state):
                if not retry_if_exception_type(exc_types)(state):
                    return False
                if state.outcome and state.outcome.exception:
                    result = giveup(state.outcome.exception)
                    if isinstance(result, bool):
                        return not result
                    if isinstance(result, (int, float)):
                        return float(result)
                    return True
                return True

            condition = wrapped
        return condition
    else:

        def pred_condition(state):
            if state.outcome is None:
                return False
            if state.outcome.exception is not None:
                return False
            return predicate(state.outcome.value)

        return pred_condition


def _retry_loop_sync(
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
    sleep,
    retry_error_callback,
    raise_on_giveup,
    max_time,
    wait_gen_kwargs,
    before=None,
    after=None,
    _holder=None,
    rate_limit=None,
    attempt_timeout=None,
):
    state = RetryState(target=target)
    start_time = _now()
    state.start_time = start_time
    call_state = RetryCallState(fn=target, start_time=start_time)
    if _holder is not None:
        _holder["state"] = state
        _holder["call_state"] = call_state
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    while True:
        if rate_limit is not None:
            if not rate_limit.acquire():
                wt = rate_limit.wait_time()
                _check_hot_loop()
                sleep(wt)
        state.tries += 1
        state.elapsed = _now() - start_time
        call_state.attempt_number = state.tries
        outcome = Attempt(tries=state.tries, elapsed=state.elapsed)

        with _retry_context_manager(state.tries):
            _call_hdlrs(on_attempt, state.to_details())

            _call_hdlrs(before, state.to_details())

            try:
                if attempt_timeout is not None:
                    _executor = ThreadPoolExecutor(max_workers=1)
                    _fut = _executor.submit(target)
                    try:
                        ret = _fut.result(timeout=attempt_timeout)
                    except _FuturesTimeoutError:
                        _fut.cancel()
                        _executor.shutdown(wait=False)
                        raise AttemptTimeoutError() from None
                    _executor.shutdown(wait=False)
                else:
                    ret = target()
            except TryAgain:
                outcome.exception = None
                outcome.value = None
                state.outcome = outcome
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                try:
                    seconds = _next_wait(wait, None, jitter, state.elapsed, max_time)
                except StopIteration:
                    break
                if stop(state):
                    break
                details = state.to_details()
                details["wait"] = seconds
                _call_hdlrs(before_sleep, details)
                _call_hdlrs(on_backoff, details)
                if seconds > 0:
                    _check_hot_loop()
                    sleep(seconds)
                continue
            except BaseException as exc:
                outcome.exception = exc
                outcome.value = None
                state.outcome = outcome
                state.idle_for += state.elapsed
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                call_state.idle_for += call_state.elapsed
                _call_hdlrs(after, state.to_details())

                if isinstance(exc, AttemptTimeoutError):
                    if stop(state):
                        details = state.to_details()
                        details["exception"] = exc
                        _call_hdlrs(on_giveup, details)
                        if retry_error_callback is not None:
                            return retry_error_callback(details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                    try:
                        seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
                    except StopIteration:
                        details = state.to_details()
                        details["exception"] = exc
                        _call_hdlrs(on_giveup, details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                    call_state.upcoming_sleep = seconds
                    details = state.to_details()
                    details["wait"] = seconds
                    details["exception"] = exc
                    _call_hdlrs(before_sleep, details)
                    _call_hdlrs(on_backoff, details)
                    if seconds > 0:
                        _check_hot_loop()
                        sleep(seconds)
                    call_state.idle_for = call_state.idle_for + seconds
                    continue

                _condition_result = condition(state)
                if _is_custom_wait(_condition_result):
                    seconds = float(_condition_result)
                    if stop(state):
                        details = state.to_details()
                        details["exception"] = exc
                        _call_hdlrs(on_giveup, details)
                        if retry_error_callback is not None:
                            return retry_error_callback(details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                elif _condition_result:
                    if stop(state):
                        details = state.to_details()
                        details["exception"] = exc
                        _call_hdlrs(on_giveup, details)
                        if retry_error_callback is not None:
                            return retry_error_callback(details)
                        if raise_on_giveup:
                            raise exc from None
                        return None

                    try:
                        seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
                    except StopIteration:
                        details = state.to_details()
                        details["exception"] = exc
                        _call_hdlrs(on_giveup, details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                else:
                    details = state.to_details()
                    details["exception"] = exc
                    _call_hdlrs(on_giveup, details)
                    if retry_error_callback is not None:
                        return retry_error_callback(details)
                    if raise_on_giveup:
                        raise exc
                    return None

                call_state.upcoming_sleep = seconds
                details = state.to_details()
                details["wait"] = seconds
                details["exception"] = exc
                _call_hdlrs(before_sleep, details)
                _call_hdlrs(on_backoff, details)
                if seconds > 0:
                    _check_hot_loop()
                    sleep(seconds)
                call_state.idle_for = call_state.idle_for + seconds
            else:
                outcome.value = ret
                outcome.exception = None
                state.outcome = outcome
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                _call_hdlrs(after, state.to_details())

                _condition_result = condition(state)
                if _is_custom_wait(_condition_result):
                    seconds = float(_condition_result)
                    if stop(state):
                        details = state.to_details()
                        details["value"] = ret
                        _call_hdlrs(on_giveup, details)
                        return ret
                    call_state.upcoming_sleep = seconds
                    details = state.to_details()
                    details["wait"] = seconds
                    details["value"] = ret
                    _call_hdlrs(before_sleep, details)
                    _call_hdlrs(on_backoff, details)
                    if seconds > 0:
                        _check_hot_loop()
                        sleep(seconds)
                    call_state.idle_for = call_state.idle_for + seconds
                elif _condition_result:
                    if stop(state):
                        details = state.to_details()
                        details["value"] = ret
                        _call_hdlrs(on_giveup, details)
                        return ret

                    try:
                        seconds = _next_wait(wait, ret, jitter, state.elapsed, max_time)
                    except StopIteration:
                        details = state.to_details()
                        details["value"] = ret
                        _call_hdlrs(on_giveup, details)
                        return ret

                    call_state.upcoming_sleep = seconds
                    details = state.to_details()
                    details["wait"] = seconds
                    details["value"] = ret
                    _call_hdlrs(before_sleep, details)
                    _call_hdlrs(on_backoff, details)
                    if seconds > 0:
                        _check_hot_loop()
                        sleep(seconds)
                    call_state.idle_for = call_state.idle_for + seconds
                else:
                    details = state.to_details()
                    details["value"] = ret
                    _call_hdlrs(on_success, details)
                    return ret


async def _retry_loop_async(
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
    sleep,
    retry_error_callback,
    raise_on_giveup,
    max_time,
    wait_gen_kwargs,
    before=None,
    after=None,
    _holder=None,
    rate_limit=None,
    attempt_timeout=None,
):
    state = RetryState(target=target)
    start_time = _now()
    state.start_time = start_time
    call_state = RetryCallState(fn=target, start_time=start_time)
    if _holder is not None:
        _holder["state"] = state
        _holder["call_state"] = call_state
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    while True:
        if rate_limit is not None:
            if not rate_limit.acquire():
                wt = rate_limit.wait_time()
                _check_hot_loop()
                await sleep(wt)
        state.tries += 1
        state.elapsed = _now() - start_time
        call_state.attempt_number = state.tries
        outcome = Attempt(tries=state.tries, elapsed=state.elapsed)

        with _retry_context_manager(state.tries):
            await _call_hdlrs_async(on_attempt, state.to_details())

            _call_hdlrs(before, state.to_details())

            try:
                if attempt_timeout is not None:
                    try:
                            ret = await asyncio.wait_for(
                                target(), timeout=attempt_timeout
                            )
                    except asyncio.TimeoutError:
                        raise AttemptTimeoutError() from None
                else:
                    ret = await target()
            except TryAgain:
                outcome.exception = None
                outcome.value = None
                state.outcome = outcome
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                try:
                    seconds = _next_wait(wait, None, jitter, state.elapsed, max_time)
                except StopIteration:
                    break
                if stop(state):
                    break
                details = state.to_details()
                details["wait"] = seconds
                await _call_hdlrs_async(before_sleep, details)
                await _call_hdlrs_async(on_backoff, details)
                if seconds > 0:
                    _check_hot_loop()
                    await sleep(seconds)
                continue
            except BaseException as exc:
                outcome.exception = exc
                outcome.value = None
                state.outcome = outcome
                state.idle_for += state.elapsed
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                call_state.idle_for += call_state.elapsed
                await _call_hdlrs_async(after, state.to_details())

                if isinstance(exc, AttemptTimeoutError):
                    if stop(state):
                        details = state.to_details()
                        details["exception"] = exc
                        await _call_hdlrs_async(on_giveup, details)
                        if retry_error_callback is not None:
                            return retry_error_callback(details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                    try:
                        seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
                    except StopIteration:
                        details = state.to_details()
                        details["exception"] = exc
                        await _call_hdlrs_async(on_giveup, details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                    call_state.upcoming_sleep = seconds
                    details = state.to_details()
                    details["wait"] = seconds
                    details["exception"] = exc
                    await _call_hdlrs_async(before_sleep, details)
                    await _call_hdlrs_async(on_backoff, details)
                    if seconds > 0:
                        _check_hot_loop()
                        await sleep(seconds)
                    call_state.idle_for = call_state.idle_for + seconds
                    continue

                _condition_result = condition(state)
                if _is_custom_wait(_condition_result):
                    seconds = float(_condition_result)
                    if stop(state):
                        details = state.to_details()
                        details["exception"] = exc
                        await _call_hdlrs_async(on_giveup, details)
                        if retry_error_callback is not None:
                            return retry_error_callback(details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                elif _condition_result:
                    if stop(state):
                        details = state.to_details()
                        details["exception"] = exc
                        await _call_hdlrs_async(on_giveup, details)
                        if retry_error_callback is not None:
                            return retry_error_callback(details)
                        if raise_on_giveup:
                            raise exc from None
                        return None

                    try:
                        seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
                    except StopIteration:
                        details = state.to_details()
                        details["exception"] = exc
                        await _call_hdlrs_async(on_giveup, details)
                        if raise_on_giveup:
                            raise exc from None
                        return None
                else:
                    details = state.to_details()
                    details["exception"] = exc
                    await _call_hdlrs_async(on_giveup, details)
                    if retry_error_callback is not None:
                        return retry_error_callback(details)
                    if raise_on_giveup:
                        raise exc
                    return None

                call_state.upcoming_sleep = seconds
                details = state.to_details()
                details["wait"] = seconds
                details["exception"] = exc
                await _call_hdlrs_async(before_sleep, details)
                await _call_hdlrs_async(on_backoff, details)
                if seconds > 0:
                    _check_hot_loop()
                    await sleep(seconds)
                call_state.idle_for = call_state.idle_for + seconds
            else:
                outcome.value = ret
                outcome.exception = None
                state.outcome = outcome
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                await _call_hdlrs_async(after, state.to_details())

                _condition_result = condition(state)
                if _is_custom_wait(_condition_result):
                    seconds = float(_condition_result)
                    if stop(state):
                        details = state.to_details()
                        details["value"] = ret
                        await _call_hdlrs_async(on_giveup, details)
                        return ret
                    call_state.upcoming_sleep = seconds
                    details = state.to_details()
                    details["wait"] = seconds
                    details["value"] = ret
                    await _call_hdlrs_async(before_sleep, details)
                    await _call_hdlrs_async(on_backoff, details)
                    if seconds > 0:
                        _check_hot_loop()
                        await sleep(seconds)
                    call_state.idle_for = call_state.idle_for + seconds
                elif _condition_result:
                    if stop(state):
                        details = state.to_details()
                        details["value"] = ret
                        await _call_hdlrs_async(on_giveup, details)
                        return ret

                    try:
                        seconds = _next_wait(wait, ret, jitter, state.elapsed, max_time)
                    except StopIteration:
                        details = state.to_details()
                        details["value"] = ret
                        await _call_hdlrs_async(on_giveup, details)
                        return ret

                    call_state.upcoming_sleep = seconds
                    details = state.to_details()
                    details["wait"] = seconds
                    details["value"] = ret
                    await _call_hdlrs_async(before_sleep, details)
                    await _call_hdlrs_async(on_backoff, details)
                    if seconds > 0:
                        _check_hot_loop()
                        await sleep(seconds)
                    call_state.idle_for = call_state.idle_for + seconds
                else:
                    details = state.to_details()
                    details["value"] = ret
                    await _call_hdlrs_async(on_success, details)
                    return ret


def _retry_sync_inner(
    target,
    wait_gen,
    *,
    condition=None,
    stop=None,
    jitter=None,
    on_success=None,
    on_backoff=None,
    on_giveup=None,
    on_attempt=None,
    before_sleep=None,
    sleep=None,
    retry_error_callback=None,
    raise_on_giveup=True,
    max_time=None,
    wait_gen_kwargs=None,
    max_tries=None,
    before=None,
    after=None,
    _holder=None,
    rate_limit=None,
    attempt_timeout=None,
):
    if not is_enabled():
        return target()
    if wait_gen_kwargs is None:
        wait_gen_kwargs = {}
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


async def _retry_async_inner(
    target,
    wait_gen,
    *,
    condition=None,
    stop=None,
    jitter=None,
    on_success=None,
    on_backoff=None,
    on_giveup=None,
    on_attempt=None,
    before_sleep=None,
    sleep=None,
    retry_error_callback=None,
    raise_on_giveup=True,
    max_time=None,
    wait_gen_kwargs=None,
    max_tries=None,
    before=None,
    after=None,
    _holder=None,
    rate_limit=None,
    attempt_timeout=None,
):
    if not is_enabled():
        return await target()
    if wait_gen_kwargs is None:
        wait_gen_kwargs = {}
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
        self._iter_state = RetryState(target=lambda: None)
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
                "Use AsyncRetryingCaller for async functions, "
                "or pass a sync function"
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
