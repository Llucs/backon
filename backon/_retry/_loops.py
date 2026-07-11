from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FuturesTimeoutError

from backon._common import _check_hot_loop, _init_wait_gen, _next_wait, _now
from backon._context import _retry_context_manager
from backon._retry._decide import (
    _call_hdlrs,
    _call_hdlrs_async,
    _decide_outcome,
    _RetryAction,
)
from backon._state import (
    Attempt,
    AttemptTimeoutError,
    RetryCallState,
    RetryState,
    TryAgain,
)


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
        if rate_limit is not None and not rate_limit.acquire():
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

            _exc = None
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
                _exc = exc
                outcome.exception = exc
                outcome.value = None
                state.outcome = outcome
                state.idle_for += state.elapsed
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                call_state.idle_for += call_state.elapsed
                _call_hdlrs(after, state.to_details())

                outcome_data = _decide_outcome(
                    state,
                    call_state,
                    wait,
                    condition,
                    stop,
                    jitter,
                    max_time,
                    exc,
                    None,
                )
                (action, seconds, details, use_retry_cb, suppress_context) = (
                    outcome_data
                )
            else:
                outcome.value = ret
                outcome.exception = None
                state.outcome = outcome
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                _call_hdlrs(after, state.to_details())

                outcome_data = _decide_outcome(
                    state,
                    call_state,
                    wait,
                    condition,
                    stop,
                    jitter,
                    max_time,
                    None,
                    ret,
                )
                (action, seconds, details, use_retry_cb, suppress_context) = (
                    outcome_data
                )

            if action == _RetryAction.SUCCESS:
                _call_hdlrs(on_success, details)
                return ret
            if action == _RetryAction.RETRY:
                _call_hdlrs(before_sleep, details)
                _call_hdlrs(on_backoff, details)
                if seconds > 0:
                    _check_hot_loop()
                    sleep(seconds)
                continue
            if _exc is not None:
                _call_hdlrs(on_giveup, details)
                if use_retry_cb and retry_error_callback is not None:
                    return retry_error_callback(details)
                if raise_on_giveup:
                    if suppress_context:
                        raise _exc from None
                    raise _exc
                return None
            _call_hdlrs(on_giveup, details)
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
        if rate_limit is not None and not rate_limit.acquire():
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

            _exc = None
            try:
                if attempt_timeout is not None:
                    try:
                        ret = await asyncio.wait_for(target(), timeout=attempt_timeout)
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
                _exc = exc
                outcome.exception = exc
                outcome.value = None
                state.outcome = outcome
                state.idle_for += state.elapsed
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                call_state.idle_for += call_state.elapsed
                await _call_hdlrs_async(after, state.to_details())

                outcome_data = _decide_outcome(
                    state,
                    call_state,
                    wait,
                    condition,
                    stop,
                    jitter,
                    max_time,
                    exc,
                    None,
                )
                (action, seconds, details, use_retry_cb, suppress_context) = (
                    outcome_data
                )
            else:
                outcome.value = ret
                outcome.exception = None
                state.outcome = outcome
                call_state.outcome = outcome
                call_state.outcome_timestamp = _now()
                await _call_hdlrs_async(after, state.to_details())

                outcome_data = _decide_outcome(
                    state,
                    call_state,
                    wait,
                    condition,
                    stop,
                    jitter,
                    max_time,
                    None,
                    ret,
                )
                (action, seconds, details, use_retry_cb, suppress_context) = (
                    outcome_data
                )

            if action == _RetryAction.SUCCESS:
                await _call_hdlrs_async(on_success, details)
                return ret
            if action == _RetryAction.RETRY:
                await _call_hdlrs_async(before_sleep, details)
                await _call_hdlrs_async(on_backoff, details)
                if seconds > 0:
                    _check_hot_loop()
                    await sleep(seconds)
                continue
            if _exc is not None:
                await _call_hdlrs_async(on_giveup, details)
                if use_retry_cb and retry_error_callback is not None:
                    return retry_error_callback(details)
                if raise_on_giveup:
                    if suppress_context:
                        raise _exc from None
                    raise _exc
                return None
            await _call_hdlrs_async(on_giveup, details)
            return ret
