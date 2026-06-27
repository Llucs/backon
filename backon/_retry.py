from __future__ import annotations

import asyncio
import logging
import operator
import time as time_module
from typing import Any, Callable, Iterable, Optional, Type, Union

from backon._common import (
    _config_handlers,
    _elapsed,
    _init_wait_gen,
    _log_backoff,
    _log_giveup,
    _maybe_call,
    _next_wait,
    _now,
    _prepare_logger,
    is_enabled,
)
from backon._jitter import full_jitter
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


def _sync_call_handlers(hdlrs, target, args, kwargs, tries, elapsed, **extra):
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


async def _async_call_handlers(handlers, target, args, kwargs, tries, elapsed, **extra):
    details = {
        "target": target,
        "args": args,
        "kwargs": kwargs,
        "tries": tries,
        "elapsed": elapsed,
    }
    details.update(extra)
    for handler in handlers:
        if asyncio.iscoroutinefunction(handler):
            await handler(details)
        else:
            handler(details)


def _retry_sync(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator,
    *,
    predicate: _Predicate[Any] = operator.not_,
    exception: Optional[_MaybeSequence[Type[Exception]]] = None,
    max_tries: Optional[_MaybeCallable[int]] = None,
    max_time: Optional[_MaybeCallable[float]] = None,
    jitter: Union[_Jitterer, None] = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
    raise_on_giveup: bool = True,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Optional[Callable[[float], Any]] = None,
    **wait_gen_kwargs: Any,
) -> Any:
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

    _sleep = sleep or time_module.sleep
    max_tries_value = _maybe_call(max_tries)
    max_time_value = _maybe_call(max_time)
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    tries = 0
    start = _now()

    while True:
        tries += 1
        elapsed = _elapsed(start)

        _sync_call_handlers(on_attempt, target, (), {}, tries, elapsed)

        if exception is not None:
            try:
                ret = target()
            except exception as e:  # type: ignore[misc]
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if giveup(e) or max_tries_exceeded or max_time_exceeded:
                    _sync_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, exception=e
                    )
                    if raise_on_giveup:
                        raise
                    return None

                try:
                    seconds = _next_wait(wait, e, jitter, elapsed, max_time_value)
                except StopIteration:
                    _sync_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, exception=e
                    )
                    raise e

                _sync_call_handlers(
                    on_backoff,
                    target,
                    (),
                    {},
                    tries,
                    elapsed,
                    wait=seconds,
                    exception=e,
                )
                _sleep(seconds)
            else:
                _sync_call_handlers(on_success, target, (), {}, tries, elapsed)
                return ret
        else:
            ret = target()
            if predicate(ret):
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if max_tries_exceeded or max_time_exceeded:
                    _sync_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, value=ret
                    )
                    return ret

                try:
                    seconds = _next_wait(wait, ret, jitter, elapsed, max_time_value)
                except StopIteration:
                    _sync_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, value=ret
                    )
                    return ret

                _sync_call_handlers(
                    on_backoff, target, (), {}, tries, elapsed, wait=seconds, value=ret
                )
                _sleep(seconds)
            else:
                _sync_call_handlers(
                    on_success, target, (), {}, tries, elapsed, value=ret
                )
                return ret


async def _retry_async(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator,
    *,
    predicate: _Predicate[Any] = operator.not_,
    exception: Optional[_MaybeSequence[Type[Exception]]] = None,
    max_tries: Optional[_MaybeCallable[int]] = None,
    max_time: Optional[_MaybeCallable[float]] = None,
    jitter: Union[_Jitterer, None] = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
    raise_on_giveup: bool = True,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Optional[Callable[[float], Any]] = None,
    **wait_gen_kwargs: Any,
) -> Any:
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

    _sleep = sleep or asyncio.sleep
    max_tries_value = _maybe_call(max_tries)
    max_time_value = _maybe_call(max_time)
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    tries = 0
    start = _now()

    while True:
        tries += 1
        elapsed = _elapsed(start)

        await _async_call_handlers(on_attempt, target, (), {}, tries, elapsed)

        if exception is not None:
            try:
                ret = await target()
            except exception as e:  # type: ignore[misc]
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if giveup(e) or max_tries_exceeded or max_time_exceeded:
                    await _async_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, exception=e
                    )
                    if raise_on_giveup:
                        raise
                    return None

                try:
                    seconds = _next_wait(wait, e, jitter, elapsed, max_time_value)
                except StopIteration:
                    await _async_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, exception=e
                    )
                    raise e

                await _async_call_handlers(
                    on_backoff,
                    target,
                    (),
                    {},
                    tries,
                    elapsed,
                    wait=seconds,
                    exception=e,
                )
                await _sleep(seconds)
            else:
                await _async_call_handlers(on_success, target, (), {}, tries, elapsed)
                return ret
        else:
            ret = await target()
            if predicate(ret):
                max_tries_exceeded = tries == max_tries_value
                max_time_exceeded = (
                    max_time_value is not None and elapsed >= max_time_value
                )

                if max_tries_exceeded or max_time_exceeded:
                    await _async_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, value=ret
                    )
                    return ret

                try:
                    seconds = _next_wait(wait, ret, jitter, elapsed, max_time_value)
                except StopIteration:
                    await _async_call_handlers(
                        on_giveup, target, (), {}, tries, elapsed, value=ret
                    )
                    return ret

                await _async_call_handlers(
                    on_backoff, target, (), {}, tries, elapsed, wait=seconds, value=ret
                )
                await _sleep(seconds)
            else:
                await _async_call_handlers(
                    on_success, target, (), {}, tries, elapsed, value=ret
                )
                return ret


def retry(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator = expo,
    *,
    predicate: _Predicate[Any] = operator.not_,
    exception: Optional[_MaybeSequence[Type[Exception]]] = None,
    max_tries: Optional[_MaybeCallable[int]] = None,
    max_time: Optional[_MaybeCallable[float]] = None,
    jitter: Union[_Jitterer, None] = full_jitter,
    giveup: _Predicate[Exception] = lambda e: False,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
    raise_on_giveup: bool = True,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Optional[Callable[[float], Any]] = None,
    **wait_gen_kwargs: Any,
) -> Any:
    if asyncio.iscoroutinefunction(target):
        return _retry_async(
            target,
            wait_gen,
            predicate=predicate,
            exception=exception,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            giveup=giveup,
            on_success=on_success,
            on_backoff=on_backoff,
            on_giveup=on_giveup,
            on_attempt=on_attempt,
            raise_on_giveup=raise_on_giveup,
            logger=logger,
            backoff_log_level=backoff_log_level,
            giveup_log_level=giveup_log_level,
            sleep=sleep,
            **wait_gen_kwargs,
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
        on_success=on_success,
        on_backoff=on_backoff,
        on_giveup=on_giveup,
        on_attempt=on_attempt,
        raise_on_giveup=raise_on_giveup,
        logger=logger,
        backoff_log_level=backoff_log_level,
        giveup_log_level=giveup_log_level,
        sleep=sleep,
        **wait_gen_kwargs,
    )


class Retrying:
    def __init__(
        self,
        wait_gen: _WaitGenerator = expo,
        *,
        predicate: _Predicate[Any] = operator.not_,
        exception: Optional[_MaybeSequence[Type[Exception]]] = None,
        max_tries: Optional[_MaybeCallable[int]] = None,
        max_time: Optional[_MaybeCallable[float]] = None,
        jitter: Union[_Jitterer, None] = full_jitter,
        giveup: _Predicate[Exception] = lambda e: False,
        on_success: Union[_Handler, Iterable[_Handler], None] = None,
        on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
        on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
        on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
        raise_on_giveup: bool = True,
        logger: _MaybeLogger = "backon",
        backoff_log_level: int = logging.INFO,
        giveup_log_level: int = logging.ERROR,
        sleep: Optional[Callable[[float], Any]] = None,
        **wait_gen_kwargs: Any,
    ):
        self._wait_gen = wait_gen
        self._predicate = predicate
        self._exception = exception
        self._max_tries = max_tries
        self._max_time = max_time
        self._jitter = jitter
        self._giveup = giveup
        self._on_success = on_success
        self._on_backoff = on_backoff
        self._on_giveup = on_giveup
        self._on_attempt = on_attempt
        self._raise_on_giveup = raise_on_giveup
        self._logger = logger
        self._backoff_log_level = backoff_log_level
        self._giveup_log_level = giveup_log_level
        self._sleep = sleep
        self._wait_gen_kwargs = wait_gen_kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        pass

    def call(self, target: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(target):

            async def wrapper():
                return await target(*args, **kwargs)

            wrapped_target = wrapper
        else:

            def wrapped_target():
                return target(*args, **kwargs)

        return retry(
            wrapped_target,
            self._wait_gen,
            predicate=self._predicate,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            giveup=self._giveup,
            on_success=self._on_success,
            on_backoff=self._on_backoff,
            on_giveup=self._on_giveup,
            on_attempt=self._on_attempt,
            raise_on_giveup=self._raise_on_giveup,
            logger=self._logger,
            backoff_log_level=self._backoff_log_level,
            giveup_log_level=self._giveup_log_level,
            sleep=self._sleep,
            **self._wait_gen_kwargs,
        )
