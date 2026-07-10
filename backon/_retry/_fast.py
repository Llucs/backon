from __future__ import annotations

import asyncio
import time as time_module

from backon._common import (
    _apply_test_overrides,
    _check_hot_loop,
    _init_wait_gen,
    _next_wait,
    _now,
    is_enabled,
)
from backon._context import _retry_context_manager
from backon._retry._helpers import _make_default_stop
from backon._retry._loops import _retry_loop_async, _retry_loop_sync
from backon._state import TryAgain


class _FastOutcome:
    __slots__ = ("exception", "value")

    def __init__(self):
        self.exception = None
        self.value = None


class _FastState:
    __slots__ = ("tries", "elapsed", "outcome")

    def __init__(self):
        self.tries = 0
        self.elapsed = 0.0
        self.outcome = _FastOutcome()


def _is_fast_path(
    condition,
    stop,
    on_success,
    on_backoff,
    on_giveup,
    on_attempt,
    before_sleep,
    before,
    after,
    retry_error_callback,
    _holder,
    jitter,
    rate_limit,
    attempt_timeout,
):
    if on_success:
        return False
    if on_backoff:
        return False
    if on_giveup:
        return False
    if on_attempt:
        return False
    if before_sleep:
        return False
    if before:
        return False
    if after:
        return False
    if retry_error_callback:
        return False
    if _holder is not None:
        return False
    if jitter is not None:
        return False
    if rate_limit is not None:
        return False
    if attempt_timeout is not None:
        return False
    return True


def _retry_fast_sync(
    target,
    wait_gen,
    condition,
    stop,
    jitter,
    max_time,
    wait_gen_kwargs,
    sleep,
    raise_on_giveup=True,
):
    state = _FastState()
    start_time = _now()
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    while True:
        state.tries += 1
        state.elapsed = _now() - start_time

        exc = None
        try:
            with _retry_context_manager(state.tries):
                ret = target()
        except TryAgain:
            state.outcome.exception = None
            state.outcome.value = None
            try:
                seconds = _next_wait(wait, None, jitter, state.elapsed, max_time)
            except StopIteration:
                break
            if stop(state):
                break
            if seconds > 0:
                _check_hot_loop()
                sleep(seconds)
            continue
        except BaseException as e:
            exc = e
            state.outcome.exception = e
            state.outcome.value = None
        else:
            state.outcome.value = ret
            state.outcome.exception = None

        if exc is not None:
            result = condition(state)
            if not result:
                if raise_on_giveup:
                    raise exc
                return None
        else:
            if not condition(state):
                return ret

        if stop(state):
            if exc is not None:
                if raise_on_giveup:
                    raise exc
                return None
            return ret

        try:
            seconds = _next_wait(
                wait,
                exc if exc is not None else ret,
                jitter,
                state.elapsed,
                max_time,
            )
        except StopIteration:
            if exc is not None:
                if raise_on_giveup:
                    raise exc from None
                return None
            return ret

        if seconds > 0:
            _check_hot_loop()
            sleep(seconds)


async def _retry_fast_async(
    target,
    wait_gen,
    condition,
    stop,
    jitter,
    max_time,
    wait_gen_kwargs,
    sleep,
    raise_on_giveup=True,
):
    state = _FastState()
    start_time = _now()
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    while True:
        state.tries += 1
        state.elapsed = _now() - start_time

        exc = None
        try:
            with _retry_context_manager(state.tries):
                ret = await target()
        except TryAgain:
            state.outcome.exception = None
            state.outcome.value = None
            try:
                seconds = _next_wait(wait, None, jitter, state.elapsed, max_time)
            except StopIteration:
                break
            if stop(state):
                break
            if seconds > 0:
                _check_hot_loop()
                await sleep(seconds)
            continue
        except BaseException as e:
            exc = e
            state.outcome.exception = e
            state.outcome.value = None
        else:
            state.outcome.value = ret
            state.outcome.exception = None

        if exc is not None:
            result = condition(state)
            if not result:
                if raise_on_giveup:
                    raise exc
                return None
        else:
            if not condition(state):
                return ret

        if stop(state):
            if exc is not None:
                if raise_on_giveup:
                    raise exc
                return None
            return ret

        try:
            seconds = _next_wait(
                wait,
                exc if exc is not None else ret,
                jitter,
                state.elapsed,
                max_time,
            )
        except StopIteration:
            if exc is not None:
                if raise_on_giveup:
                    raise exc from None
                return None
            return ret

        if seconds > 0:
            _check_hot_loop()
            await sleep(seconds)


def _retry_fast_sync_inner(
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

    if _is_fast_path(
        condition,
        stop,
        on_success,
        on_backoff,
        on_giveup,
        on_attempt,
        before_sleep,
        before,
        after,
        retry_error_callback,
        _holder,
        jitter,
        rate_limit,
        attempt_timeout,
    ):
        max_tries, max_time = _apply_test_overrides(max_tries, max_time)
        if stop is None:
            stop = _make_default_stop(max_tries, max_time)
        _sleep = sleep or time_module.sleep
        return _retry_fast_sync(
            target,
            wait_gen,
            condition,
            stop,
            jitter,
            max_time,
            wait_gen_kwargs,
            _sleep,
            raise_on_giveup=raise_on_giveup,
        )

    max_tries, max_time = _apply_test_overrides(max_tries, max_time)
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


async def _retry_fast_async_inner(
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

    if _is_fast_path(
        condition,
        stop,
        on_success,
        on_backoff,
        on_giveup,
        on_attempt,
        before_sleep,
        before,
        after,
        retry_error_callback,
        _holder,
        jitter,
        rate_limit,
        attempt_timeout,
    ):
        max_tries, max_time = _apply_test_overrides(max_tries, max_time)
        if stop is None:
            stop = _make_default_stop(max_tries, max_time)
        _sleep = sleep or asyncio.sleep
        return await _retry_fast_async(
            target,
            wait_gen,
            condition,
            stop,
            jitter,
            max_time,
            wait_gen_kwargs,
            _sleep,
            raise_on_giveup=raise_on_giveup,
        )

    max_tries, max_time = _apply_test_overrides(max_tries, max_time)
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
