import asyncio
import logging
import operator
import time as time_module
from typing import Any, Callable, Iterable, Optional, Type, Union

from backon import _async, _sync
from backon._common import (
    _config_handlers,
    _log_backoff,
    _log_giveup,
    _prepare_logger,
)
from backon._jitter import full_jitter
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
    max_tries: Optional[_MaybeCallable[int]] = None,
    max_time: Optional[_MaybeCallable[float]] = None,
    jitter: Union[_Jitterer, None] = full_jitter,
    on_success: Union[_Handler, Iterable[_Handler], None] = None,
    on_backoff: Union[_Handler, Iterable[_Handler], None] = None,
    on_giveup: Union[_Handler, Iterable[_Handler], None] = None,
    on_attempt: Union[_Handler, Iterable[_Handler], None] = None,
    logger: _MaybeLogger = "backon",
    backoff_log_level: int = logging.INFO,
    giveup_log_level: int = logging.ERROR,
    sleep: Optional[Callable[[float], Any]] = None,
    **wait_gen_kwargs: Any,
) -> Callable[[_CallableT], _CallableT]:
    def decorate(target):
        nonlocal logger, on_success, on_backoff, on_giveup, on_attempt

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

        if asyncio.iscoroutinefunction(target):
            retry = _async.retry_predicate
            _sleep = sleep or asyncio.sleep
        else:
            retry = _sync.retry_predicate
            _sleep = sleep or time_module.sleep

        return retry(
            target,
            wait_gen,
            predicate,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            on_success=on_success,
            on_backoff=on_backoff,
            on_giveup=on_giveup,
            on_attempt=on_attempt,
            sleep=_sleep,
            wait_gen_kwargs=wait_gen_kwargs,
        )

    return decorate


def on_exception(
    wait_gen: _WaitGenerator,
    exception: _MaybeSequence[Type[Exception]],
    *,
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
) -> Callable[[_CallableT], _CallableT]:
    def decorate(target):
        nonlocal logger, on_success, on_backoff, on_giveup, on_attempt

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

        if asyncio.iscoroutinefunction(target):
            retry = _async.retry_exception
            _sleep = sleep or asyncio.sleep
        else:
            retry = _sync.retry_exception
            _sleep = sleep or time_module.sleep

        return retry(
            target,
            wait_gen,
            exception,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            giveup=giveup,
            on_success=on_success,
            on_backoff=on_backoff,
            on_giveup=on_giveup,
            on_attempt=on_attempt,
            raise_on_giveup=raise_on_giveup,
            sleep=_sleep,
            wait_gen_kwargs=wait_gen_kwargs,
        )

    return decorate
