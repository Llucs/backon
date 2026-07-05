from __future__ import annotations

import asyncio
import time as time_module

from backon._common import _apply_test_overrides, is_enabled
from backon._retry._helpers import _make_default_stop
from backon._retry._loops import _retry_loop_async, _retry_loop_sync


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
