from __future__ import annotations

import asyncio
import functools
import inspect
import operator
from collections.abc import Awaitable, Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor
from concurrent.futures import wait as futures_wait
from typing import Any, TypeVar, cast

from backon._jitter import full_jitter
from backon._retry import _retry_async_inner, _retry_sync_inner
from backon._retry._helpers import _make_default_condition
from backon._typing import (
    P,
    R,
    _Handler,
    _Jitterer,
    _MaybeCallable,
    _MaybeSequence,
    _Predicate,
    _WaitGenerator,
)
from backon._wait_gen import expo

T = TypeVar("T")


class HedgeError(Exception):
    pass


def hedge(
    target: Callable[P, R],
    wait_gen: _WaitGenerator = expo,
    *,
    max_hedge: int = 3,
    exception: _MaybeSequence[type[Exception]] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    on_hedge: _Handler | Iterable[_Handler] | None = None,
    timeout: float | None = None,
    predicate: _Predicate[Any] = operator.not_,
    **wait_gen_kwargs: Any,
) -> R:
    if inspect.iscoroutinefunction(target):
        return cast(
            R,
            _hedge_async(
                target,
                wait_gen,
                max_hedge=max_hedge,
                exception=exception,
                max_tries=max_tries,
                max_time=max_time,
                jitter=jitter,
                on_hedge=on_hedge,
                timeout=timeout,
                predicate=predicate,
                **wait_gen_kwargs,
            ),
        )
    return _hedge_sync(
        target,
        wait_gen,
        max_hedge=max_hedge,
        exception=exception,
        max_tries=max_tries,
        max_time=max_time,
        jitter=jitter,
        on_hedge=on_hedge,
        timeout=timeout,
        predicate=predicate,
        **wait_gen_kwargs,
    )


def _make_hedge_target(target, args, kwargs):
    return lambda: target(*args, **kwargs)


def _hedge_sync(
    target: Callable[..., T],
    wait_gen: _WaitGenerator = expo,
    *,
    max_hedge: int = 3,
    exception: _MaybeSequence[type[Exception]] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    on_hedge: _Handler | Iterable[_Handler] | None = None,
    timeout: float | None = None,
    predicate: _Predicate[Any] = operator.not_,
    **wait_gen_kwargs: Any,
) -> T:
    on_hedge_list = []
    if on_hedge is not None:
        on_hedge_list = list(on_hedge) if hasattr(on_hedge, "__iter__") else [on_hedge]

    condition = _make_default_condition(exception, None, predicate)

    first_exc = None
    with ThreadPoolExecutor(max_workers=max_hedge) as executor:
        futures = set()
        for _i in range(max_hedge):
            fut = executor.submit(
                _retry_sync_inner,
                _make_hedge_target(target, (), {}),
                wait_gen,
                condition=condition,
                max_tries=max_tries,
                max_time=max_time,
                jitter=jitter,
                on_success=None,
                on_backoff=None,
                on_giveup=None,
                on_attempt=None,
                before_sleep=None,
                sleep=None,
                retry_error_callback=None,
                raise_on_giveup=True,
                wait_gen_kwargs=wait_gen_kwargs,
            )
            futures.add(fut)

        for handler in on_hedge_list:
            handler({"max_hedge": max_hedge, "target": target, "hedge_count": _i + 1})  # type: ignore[typeddict-item, typeddict-unknown-key]

        done, not_done = futures_wait(
            futures,
            timeout=timeout,
            return_when=FIRST_COMPLETED,
        )

        for fut in not_done:
            fut.cancel()

        for fut in done:
            exc = fut.exception()
            if exc is None:
                return cast(T, fut.result())
            if first_exc is None:
                first_exc = exc

        if first_exc is not None:
            raise first_exc
        raise HedgeError("all hedged requests failed")


async def _hedge_async(
    target: Callable[..., T],
    wait_gen: _WaitGenerator = expo,
    *,
    max_hedge: int = 3,
    exception: _MaybeSequence[type[Exception]] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    on_hedge: _Handler | Iterable[_Handler] | None = None,
    timeout: float | None = None,
    predicate: _Predicate[Any] = operator.not_,
    **wait_gen_kwargs: Any,
) -> T:
    on_hedge_list = []
    if on_hedge is not None:
        on_hedge_list = list(on_hedge) if hasattr(on_hedge, "__iter__") else [on_hedge]

    condition = _make_default_condition(exception, None, predicate)

    async def run_hedge():
        return await _retry_async_inner(
            lambda: target(*(), **{}),
            wait_gen,
            condition=condition,
            max_tries=max_tries,
            max_time=max_time,
            jitter=jitter,
            on_success=None,
            on_backoff=None,
            on_giveup=None,
            on_attempt=None,
            before_sleep=None,
            sleep=None,
            retry_error_callback=None,
            raise_on_giveup=True,
            wait_gen_kwargs=wait_gen_kwargs,
        )

    tasks = [asyncio.create_task(run_hedge()) for _ in range(max_hedge)]

    for handler in on_hedge_list:
        handler({"max_hedge": max_hedge, "target": target, "hedge_count": len(tasks)})  # type: ignore[typeddict-item, typeddict-unknown-key]

    done, pending = await asyncio.wait(
        tasks,
        timeout=timeout,
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()

    first_exc = None
    for task in done:
        exc = task.exception()
        if exc is None:
            return cast(T, task.result())
        if first_exc is None:
            first_exc = exc

    if first_exc is not None:
        raise first_exc
    raise HedgeError("all hedged requests failed")


def on_hedge(
    wait_gen: _WaitGenerator = expo,
    *,
    max_hedge: int = 3,
    exception: _MaybeSequence[type[Exception]] | None = None,
    max_tries: _MaybeCallable[int] | None = None,
    max_time: _MaybeCallable[float] | None = None,
    jitter: _Jitterer | None = full_jitter,
    on_hedge: _Handler | Iterable[_Handler] | None = None,
    timeout: float | None = None,
    **wait_gen_kwargs: Any,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(target: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(target):

            @functools.wraps(target)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                return cast(
                    R,
                    await _hedge_async(
                        _make_hedge_target(target, args, kwargs),
                        wait_gen,
                        max_hedge=max_hedge,
                        exception=exception,
                        max_tries=max_tries,
                        max_time=max_time,
                        jitter=jitter,
                        on_hedge=on_hedge,
                        timeout=timeout,
                        predicate=operator.not_,
                        **wait_gen_kwargs,
                    ),
                )

            return cast(Callable[P, R], wrapper)
        else:

            @functools.wraps(target)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                return cast(
                    R,
                    _hedge_sync(
                        _make_hedge_target(target, args, kwargs),
                        wait_gen,
                        max_hedge=max_hedge,
                        exception=exception,
                        max_tries=max_tries,
                        max_time=max_time,
                        jitter=jitter,
                        on_hedge=on_hedge,
                        timeout=timeout,
                        predicate=operator.not_,
                        **wait_gen_kwargs,
                    ),
                )

            return cast(Callable[P, R], wrapper)

    return decorate


class HedgingRetrying:
    def __init__(
        self,
        wait_gen: _WaitGenerator = expo,
        *,
        max_hedge: int = 3,
        exception: _MaybeSequence[type[Exception]] | None = None,
        max_tries: _MaybeCallable[int] | None = None,
        max_time: _MaybeCallable[float] | None = None,
        jitter: _Jitterer | None = full_jitter,
        on_hedge: _Handler | Iterable[_Handler] | None = None,
        timeout: float | None = None,
        **wait_gen_kwargs: Any,
    ) -> None:
        self._wait_gen = wait_gen
        self._max_hedge = max_hedge
        self._exception = exception
        self._max_tries = max_tries
        self._max_time = max_time
        self._jitter = jitter
        self._on_hedge = on_hedge
        self._timeout = timeout
        self._wait_gen_kwargs = wait_gen_kwargs

    def __enter__(self) -> HedgingRetrying:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        pass

    async def __aenter__(self) -> HedgingRetrying:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        pass

    def call(self, target: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        if inspect.iscoroutinefunction(target):
            raise TypeError("Use async_call for async functions")

        def wrapped() -> T:
            return target(*args, **kwargs)

        return _hedge_sync(
            wrapped,
            self._wait_gen,
            max_hedge=self._max_hedge,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            on_hedge=self._on_hedge,
            timeout=self._timeout,
            predicate=operator.not_,
            **self._wait_gen_kwargs,
        )

    async def async_call(
        self, target: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        async def wrapped():
            return await target(*args, **kwargs)

        return await _hedge_async(
            wrapped,
            self._wait_gen,
            max_hedge=self._max_hedge,
            exception=self._exception,
            max_tries=self._max_tries,
            max_time=self._max_time,
            jitter=self._jitter,
            on_hedge=self._on_hedge,
            timeout=self._timeout,
            predicate=operator.not_,
            **self._wait_gen_kwargs,
        )
