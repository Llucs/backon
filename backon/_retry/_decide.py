from __future__ import annotations

import inspect
from enum import Enum, auto

from backon._common import _is_custom_wait, _next_wait
from backon._state import AttemptTimeoutError


class _RetryAction(Enum):
    GIVEUP = auto()
    SUCCESS = auto()
    RETRY = auto()


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


def _decide_outcome(
    state,
    call_state,
    wait,
    condition,
    stop,
    jitter,
    max_time,
    exc,
    ret,
):
    details = state.to_details()

    if exc is not None:
        details["exception"] = exc

        if isinstance(exc, AttemptTimeoutError):
            if stop(state):
                return (_RetryAction.GIVEUP, None, details, True, True)
            try:
                seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
            except StopIteration:
                return (_RetryAction.GIVEUP, None, details, False, True)
            if state.outcome is not None:
                state.outcome.wait = seconds
            if stop(state):
                return (_RetryAction.GIVEUP, None, details, True, True)
            call_state.upcoming_sleep = seconds
            details["wait"] = seconds
            call_state.idle_for = call_state.idle_for + seconds
            return (_RetryAction.RETRY, seconds, details, True, False)

        _condition_result = condition(state)
        if _is_custom_wait(_condition_result):
            seconds = float(_condition_result)
            if state.outcome is not None:
                state.outcome.wait = seconds
            if stop(state):
                return (_RetryAction.GIVEUP, None, details, True, True)
            call_state.upcoming_sleep = seconds
            details["wait"] = seconds
            call_state.idle_for = call_state.idle_for + seconds
            return (_RetryAction.RETRY, seconds, details, True, False)
        if _condition_result:
            try:
                seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
            except StopIteration:
                return (_RetryAction.GIVEUP, None, details, False, True)
            if state.outcome is not None:
                state.outcome.wait = seconds
            if stop(state):
                return (_RetryAction.GIVEUP, None, details, True, True)
            call_state.upcoming_sleep = seconds
            details["wait"] = seconds
            call_state.idle_for = call_state.idle_for + seconds
            return (_RetryAction.RETRY, seconds, details, True, False)
        return (_RetryAction.GIVEUP, None, details, True, False)

    if ret is not None:
        details["value"] = ret

    _condition_result = condition(state)
    if _is_custom_wait(_condition_result):
        seconds = float(_condition_result)
        if state.outcome is not None:
            state.outcome.wait = seconds
        if stop(state):
            return (_RetryAction.GIVEUP, None, details, True, False)
        call_state.upcoming_sleep = seconds
        details["wait"] = seconds
        call_state.idle_for = call_state.idle_for + seconds
        return (_RetryAction.RETRY, seconds, details, True, False)
    if _condition_result:
        try:
            seconds = _next_wait(wait, ret, jitter, state.elapsed, max_time)
        except StopIteration:
            return (_RetryAction.GIVEUP, None, details, True, False)
        if state.outcome is not None:
            state.outcome.wait = seconds
        if stop(state):
            return (_RetryAction.GIVEUP, None, details, True, False)
        call_state.upcoming_sleep = seconds
        details["wait"] = seconds
        call_state.idle_for = call_state.idle_for + seconds
        return (_RetryAction.RETRY, seconds, details, True, False)
    return (_RetryAction.SUCCESS, None, details, True, False)
