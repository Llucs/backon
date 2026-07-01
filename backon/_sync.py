import functools
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FuturesTimeoutError

from backon._common import (
    _elapsed,
    _init_wait_gen,
    _maybe_call,
    _next_wait,
    _now,
    is_enabled,
)
from backon._state import AttemptTimeoutError


def _unwrap(target):
    if isinstance(target, staticmethod):
        return target.__func__
    return target


def _call_handlers(hdlrs, target, args, kwargs, tries, elapsed, **extra):
    details = {
        "target": target,
        "args": args,
        "kwargs": kwargs,
        "tries": tries,
        "elapsed": elapsed,
    }
    details.update(extra)
    for hdlr in hdlrs:
        hdlr(details)


def retry_predicate(
    target,
    wait_gen,
    predicate,
    *,
    max_tries,
    max_time,
    jitter,
    on_success,
    on_backoff,
    on_giveup,
    on_attempt,
    sleep,
    wait_gen_kwargs,
    attempt_timeout=None,
):
    target = _unwrap(target)

    @functools.wraps(target)
    def retry(*args, **kwargs):
        if not is_enabled():
            return target(*args, **kwargs)

        max_tries_value = _maybe_call(max_tries)
        max_time_value = _maybe_call(max_time)

        tries = 0
        start = _now()
        wait = _init_wait_gen(wait_gen, wait_gen_kwargs)
        while True:
            tries += 1
            elapsed = _elapsed(start)
            details = {
                "target": target,
                "args": args,
                "kwargs": kwargs,
                "tries": tries,
                "elapsed": elapsed,
            }

            _call_handlers(on_attempt, **details)

            try:
                if attempt_timeout is not None:
                    with ThreadPoolExecutor(max_workers=1) as _executor:
                        fut = _executor.submit(target, *args, **kwargs)
                        try:
                            ret = fut.result(timeout=attempt_timeout)
                        except _FuturesTimeoutError:
                            raise AttemptTimeoutError() from None
                else:
                    ret = target(*args, **kwargs)
            except AttemptTimeoutError:
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )
                if max_tries_exceeded or max_time_exceeded:
                    _call_handlers(on_giveup, **details)
                    break
                try:
                    seconds = _next_wait(wait, None, jitter, elapsed, max_time_value)
                except StopIteration:
                    _call_handlers(on_giveup, **details)
                    break
                _call_handlers(on_backoff, **details, wait=seconds)
                sleep(seconds)
                continue
            if predicate(ret):
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if max_tries_exceeded or max_time_exceeded:
                    _call_handlers(on_giveup, **details, value=ret)
                    break

                try:
                    seconds = _next_wait(wait, ret, jitter, elapsed, max_time_value)
                except StopIteration:
                    _call_handlers(on_giveup, **details)
                    break

                _call_handlers(on_backoff, **details, value=ret, wait=seconds)

                sleep(seconds)
                continue
            else:
                _call_handlers(on_success, **details, value=ret)
                break

        return ret

    return retry


def retry_exception(
    target,
    wait_gen,
    exception,
    *,
    max_tries,
    max_time,
    jitter,
    giveup,
    on_success,
    on_backoff,
    on_giveup,
    on_attempt,
    raise_on_giveup,
    sleep,
    wait_gen_kwargs,
    attempt_timeout=None,
):
    target = _unwrap(target)

    @functools.wraps(target)
    def retry(*args, **kwargs):
        if not is_enabled():
            return target(*args, **kwargs)

        max_tries_value = _maybe_call(max_tries)
        max_time_value = _maybe_call(max_time)

        tries = 0
        start = _now()
        wait = _init_wait_gen(wait_gen, wait_gen_kwargs)
        while True:
            tries += 1
            elapsed = _elapsed(start)
            details = {
                "target": target,
                "args": args,
                "kwargs": kwargs,
                "tries": tries,
                "elapsed": elapsed,
            }

            _call_handlers(on_attempt, **details)

            try:
                if attempt_timeout is not None:
                    with ThreadPoolExecutor(max_workers=1) as _executor:
                        fut = _executor.submit(target, *args, **kwargs)
                        try:
                            ret = fut.result(timeout=attempt_timeout)
                        except _FuturesTimeoutError:
                            raise AttemptTimeoutError() from None
                else:
                    ret = target(*args, **kwargs)
            except AttemptTimeoutError:
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )
                if max_tries_exceeded or max_time_exceeded:
                    _call_handlers(on_giveup, **details)
                    if raise_on_giveup:
                        raise
                    return None
                try:
                    seconds = _next_wait(wait, None, jitter, elapsed, max_time_value)
                except StopIteration:
                    _call_handlers(on_giveup, **details)
                    if raise_on_giveup:
                        raise
                    return None
                _call_handlers(on_backoff, **details, wait=seconds)
                sleep(seconds)
            except exception as e:
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if giveup(e) or max_tries_exceeded or max_time_exceeded:
                    _call_handlers(on_giveup, **details, exception=e)
                    if raise_on_giveup:
                        raise
                    return None

                try:
                    seconds = _next_wait(wait, e, jitter, elapsed, max_time_value)
                except StopIteration:
                    _call_handlers(on_giveup, **details, exception=e)
                    raise e from None

                _call_handlers(on_backoff, **details, wait=seconds, exception=e)

                sleep(seconds)
            else:
                _call_handlers(on_success, **details)
                return ret

    return retry
