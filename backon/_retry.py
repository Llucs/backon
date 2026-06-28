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
from backon._jitter import full_jitter
from backon._state import Attempt, RetryState, TryAgain
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


def _sync_call_handlers(hdlrs, details):
    if not hdlrs:
        return
    for hdlr in hdlrs:
        hdlr(details)


async def _async_call_handlers(handlers, details):
    if not handlers:
        return
    for handler in handlers:
        if asyncio.iscoroutinefunction(handler):
            await handler(details)
        else:
            handler(details)


def _make_default_stop(max_tries, max_time):
    stops = []
    if max_tries is not None:
        stops.append(stop_after_attempt(max_tries))
    if max_time is not None:
        stops.append(stop_after_delay(max_time))
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
                    return not giveup(state.outcome.exception)
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
):
    state = RetryState(target=target)
    state.start_time = _now()
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    while True:
        state.tries += 1
        state.elapsed = _elapsed(state.start_time)
        outcome = Attempt(tries=state.tries, elapsed=state.elapsed)

        _sync_call_handlers(on_attempt, state.to_details())

        try:
            ret = target()
        except TryAgain:
            outcome.exception = None
            outcome.value = None
            state.outcome = outcome
            try:
                seconds = _next_wait(wait, None, jitter, state.elapsed, max_time)
            except StopIteration:
                break
            if stop(state):
                break
            details = state.to_details()
            details["wait"] = seconds
            _sync_call_handlers(before_sleep, details)
            _sync_call_handlers(on_backoff, details)
            sleep(seconds)
            continue
        except BaseException as exc:
            outcome.exception = exc
            outcome.value = None
            state.outcome = outcome
            state.idle_for += state.elapsed

            if not condition(state):
                details = state.to_details()
                details["exception"] = exc
                _sync_call_handlers(on_giveup, details)
                if retry_error_callback is not None:
                    return retry_error_callback(details)
                if raise_on_giveup:
                    raise exc
                return None

            if stop(state):
                details = state.to_details()
                details["exception"] = exc
                _sync_call_handlers(on_giveup, details)
                if retry_error_callback is not None:
                    return retry_error_callback(details)
                if raise_on_giveup:
                    raise exc
                return None

            try:
                seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
            except StopIteration:
                details = state.to_details()
                details["exception"] = exc
                _sync_call_handlers(on_giveup, details)
                if raise_on_giveup:
                    raise exc
                return None

            details = state.to_details()
            details["wait"] = seconds
            details["exception"] = exc
            _sync_call_handlers(before_sleep, details)
            _sync_call_handlers(on_backoff, details)
            sleep(seconds)
        else:
            outcome.value = ret
            outcome.exception = None
            state.outcome = outcome

            if condition(state):
                if stop(state):
                    details = state.to_details()
                    details["value"] = ret
                    _sync_call_handlers(on_giveup, details)
                    return ret

                try:
                    seconds = _next_wait(wait, ret, jitter, state.elapsed, max_time)
                except StopIteration:
                    details = state.to_details()
                    details["value"] = ret
                    _sync_call_handlers(on_giveup, details)
                    return ret

                details = state.to_details()
                details["wait"] = seconds
                details["value"] = ret
                _sync_call_handlers(before_sleep, details)
                _sync_call_handlers(on_backoff, details)
                sleep(seconds)
            else:
                details = state.to_details()
                details["value"] = ret
                _sync_call_handlers(on_success, details)
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
):
    state = RetryState(target=target)
    state.start_time = _now()
    wait = _init_wait_gen(wait_gen, wait_gen_kwargs)

    while True:
        state.tries += 1
        state.elapsed = _elapsed(state.start_time)
        outcome = Attempt(tries=state.tries, elapsed=state.elapsed)

        await _async_call_handlers(on_attempt, state.to_details())

        try:
            ret = await target()
        except TryAgain:
            outcome.exception = None
            outcome.value = None
            state.outcome = outcome
            try:
                seconds = _next_wait(wait, None, jitter, state.elapsed, max_time)
            except StopIteration:
                break
            if stop(state):
                break
            details = state.to_details()
            details["wait"] = seconds
            await _async_call_handlers(before_sleep, details)
            await _async_call_handlers(on_backoff, details)
            await sleep(seconds)
            continue
        except BaseException as exc:
            outcome.exception = exc
            outcome.value = None
            state.outcome = outcome
            state.idle_for += state.elapsed

            if not condition(state):
                details = state.to_details()
                details["exception"] = exc
                await _async_call_handlers(on_giveup, details)
                if retry_error_callback is not None:
                    return retry_error_callback(details)
                if raise_on_giveup:
                    raise exc
                return None

            if stop(state):
                details = state.to_details()
                details["exception"] = exc
                await _async_call_handlers(on_giveup, details)
                if retry_error_callback is not None:
                    return retry_error_callback(details)
                if raise_on_giveup:
                    raise exc
                return None

            try:
                seconds = _next_wait(wait, exc, jitter, state.elapsed, max_time)
            except StopIteration:
                details = state.to_details()
                details["exception"] = exc
                await _async_call_handlers(on_giveup, details)
                if raise_on_giveup:
                    raise exc
                return None

            details = state.to_details()
            details["wait"] = seconds
            details["exception"] = exc
            await _async_call_handlers(before_sleep, details)
            await _async_call_handlers(on_backoff, details)
            await sleep(seconds)
        else:
            outcome.value = ret
            outcome.exception = None
            state.outcome = outcome

            if condition(state):
                if stop(state):
                    details = state.to_details()
                    details["value"] = ret
                    await _async_call_handlers(on_giveup, details)
                    return ret

                try:
                    seconds = _next_wait(wait, ret, jitter, state.elapsed, max_time)
                except StopIteration:
                    details = state.to_details()
                    details["value"] = ret
                    await _async_call_handlers(on_giveup, details)
                    return ret

                details = state.to_details()
                details["wait"] = seconds
                details["value"] = ret
                await _async_call_handlers(before_sleep, details)
                await _async_call_handlers(on_backoff, details)
                await sleep(seconds)
            else:
                details = state.to_details()
                details["value"] = ret
                await _async_call_handlers(on_success, details)
                return ret


def _retry_sync(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator,
    *,
    condition: Optional[RetryCondition] = None,
    stop: Optional[Stop] = None,
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
    before_sleep: Union[_Handler, Iterable[_Handler], None] = None,
    retry_error_callback: Optional[Callable[[dict], Any]] = None,
    raise_on_giveup: bool = True,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Optional[Callable[[float], Any]] = None,
    wait_gen_kwargs: dict = {},
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
    before_sleep = _config_handlers(before_sleep)

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
    )


async def _retry_async(
    target: Callable[..., Any],
    wait_gen: _WaitGenerator,
    *,
    condition: Optional[RetryCondition] = None,
    stop: Optional[Stop] = None,
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
    before_sleep: Union[_Handler, Iterable[_Handler], None] = None,
    retry_error_callback: Optional[Callable[[dict], Any]] = None,
    raise_on_giveup: bool = True,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Optional[Callable[[float], Any]] = None,
    wait_gen_kwargs: dict = {},
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
    before_sleep = _config_handlers(before_sleep)

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
    )


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
    condition: Optional[RetryCondition] = None,
    stop: Optional[Stop] = None,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
    before_sleep: Union[_Handler, Iterable[_Handler], None] = None,
    retry_error_callback: Optional[Callable[[dict], Any]] = None,
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
        condition: Optional[RetryCondition] = None,
        stop: Optional[Stop] = None,
        on_success: Union[_Handler, Iterable[_Handler], None] = None,
        on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
        on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
        on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
        before_sleep: Union[_Handler, Iterable[_Handler], None] = None,
        retry_error_callback: Optional[Callable[[dict], Any]] = None,
        raise_on_giveup: bool = True,
        logger: _MaybeLogger = "backon",
        backoff_log_level: int = logging.INFO,
        giveup_log_level: int = logging.ERROR,
        sleep: Optional[Callable[[float], Any]] = None,
        enabled: bool = True,
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
        self._wait_gen_kwargs = wait_gen_kwargs
        self._state: Optional[RetryState] = None

    @property
    def statistics(self) -> dict:
        if self._state is None:
            return {}
        return self._state.statistics

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

    def call(self, target: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(target):
            raise TypeError(
                "Use await with Retrying.call() for async functions, "
                "or pass a sync function"
            )

        def wrapped():
            return target(*args, **kwargs)

        return _retry_sync(
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
        )

    async def async_call(
        self, target: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        async def wrapped():
            return await target(*args, **kwargs)

        return await _retry_async(
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
        )


def sleep_using_event(event) -> Callable[[float], None]:
    def sleep(seconds: float) -> None:
        event.wait(timeout=seconds)

    return sleep
