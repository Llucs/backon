import asyncio
import functools

from backon._common import (
    _elapsed,
    _init_wait_gen,
    _maybe_call,
    _next_wait,
    _now,
    is_enabled,
)


def _unwrap(target):
    if isinstance(target, staticmethod):
        return target.__func__
    return target


def _ensure_coroutine(coro_or_func):
    if asyncio.iscoroutinefunction(coro_or_func):
        return coro_or_func
    else:

        @functools.wraps(coro_or_func)
        async def f(*args, **kwargs):
            return coro_or_func(*args, **kwargs)

        return f


def _ensure_coroutines(coros_or_funcs):
    return [_ensure_coroutine(f) for f in coros_or_funcs]


async def _call_handlers(handlers, *, target, args, kwargs, tries, elapsed, **extra):
    details = {
        "target": target,
        "args": args,
        "kwargs": kwargs,
        "tries": tries,
        "elapsed": elapsed,
    }
    details.update(extra)
    for handler in handlers:
        await handler(details)


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
):
    target = _unwrap(target)
    on_success = _ensure_coroutines(on_success)
    on_backoff = _ensure_coroutines(on_backoff)
    on_giveup = _ensure_coroutines(on_giveup)
    on_attempt = _ensure_coroutines(on_attempt)

    assert not asyncio.iscoroutinefunction(max_tries)
    assert not asyncio.iscoroutinefunction(jitter)

    assert asyncio.iscoroutinefunction(target)

    @functools.wraps(target)
    async def retry(*args, **kwargs):
        if not is_enabled():
            return await target(*args, **kwargs)

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

            await _call_handlers(on_attempt, **details)

            ret = await target(*args, **kwargs)
            if predicate(ret):
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if max_tries_exceeded or max_time_exceeded:
                    await _call_handlers(on_giveup, **details, value=ret)
                    break

                try:
                    seconds = _next_wait(wait, ret, jitter, elapsed, max_time_value)
                except StopIteration:
                    await _call_handlers(on_giveup, **details, value=ret)
                    break

                await _call_handlers(on_backoff, **details, value=ret, wait=seconds)

                await sleep(seconds)
                continue
            else:
                await _call_handlers(on_success, **details, value=ret)
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
):
    target = _unwrap(target)
    on_success = _ensure_coroutines(on_success)
    on_backoff = _ensure_coroutines(on_backoff)
    on_giveup = _ensure_coroutines(on_giveup)
    on_attempt = _ensure_coroutines(on_attempt)
    giveup = _ensure_coroutine(giveup)

    assert not asyncio.iscoroutinefunction(max_tries)
    assert not asyncio.iscoroutinefunction(jitter)

    @functools.wraps(target)
    async def retry(*args, **kwargs):
        if not is_enabled():
            return await target(*args, **kwargs)

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

            await _call_handlers(on_attempt, **details)

            try:
                ret = await target(*args, **kwargs)
            except exception as e:
                giveup_result = await giveup(e)
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if giveup_result or max_tries_exceeded or max_time_exceeded:
                    await _call_handlers(on_giveup, **details, exception=e)
                    if raise_on_giveup:
                        raise
                    return None

                try:
                    seconds = _next_wait(wait, e, jitter, elapsed, max_time_value)
                except StopIteration:
                    await _call_handlers(on_giveup, **details, exception=e)
                    raise e from None

                await _call_handlers(on_backoff, **details, wait=seconds, exception=e)

                await sleep(seconds)
            else:
                await _call_handlers(on_success, **details)
                return ret

    return retry
