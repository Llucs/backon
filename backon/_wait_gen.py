from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Generator, Iterable, Sequence
from typing import Any


class _Wait:
    def __init__(self, gen_func: Callable[..., Generator[float, Any, None]]) -> None:
        self._gen_func = gen_func

    def __call__(self, **kwargs: Any) -> Generator[float, Any, None]:
        return self._gen_func(**kwargs)

    def __add__(self, other: _Wait | _CombinedWait) -> _CombinedWait:
        if isinstance(other, _CombinedWait):
            return _CombinedWait(self, *other._waits)
        return _CombinedWait(self, other)

    def __radd__(self, other: _Wait) -> _CombinedWait:
        return _CombinedWait(other, self)


class _CombinedWait:
    def __init__(self, *waits: _Wait) -> None:
        self._waits = waits

    def __call__(self, **kwargs: Any) -> Generator[float, Any, None]:
        gens = [w(**kwargs) for w in self._waits]
        for g in gens:
            next(g)
        value = yield 0.0
        while True:
            total = 0.0
            for g in gens:
                total += g.send(value)
            value = yield total

    def __add__(self, other: _Wait | _CombinedWait) -> _CombinedWait:
        if isinstance(other, _CombinedWait):
            return _CombinedWait(*self._waits, *other._waits)
        return _CombinedWait(*self._waits, other)


def _expo(
    base: float = 2, factor: float = 1, max_value: float | None = None
) -> Generator[float, Any, None]:
    yield 0.0
    n = 0
    while True:
        a = factor * base**n
        if max_value is None or a < max_value:
            yield a
            n += 1
        else:
            yield max_value


expo = _Wait(_expo)


def _decay(
    initial_value: float = 1, decay_factor: float = 1, min_value: float | None = None
) -> Generator[float, Any, None]:
    yield 0.0
    t = 0
    while True:
        a = initial_value * math.e ** (-t * decay_factor)
        if min_value is None or a > min_value:
            yield a
            t += 1
        else:
            yield min_value


decay = _Wait(_decay)


def _fibo(max_value: int | None = None) -> Generator[int, None, None]:
    yield 0
    a = 1
    b = 1
    while True:
        if max_value is None or a < max_value:
            yield a
            a, b = b, a + b
        else:
            yield max_value


fibo = _Wait(_fibo)


def _constant(
    interval: int | float | Sequence[float] = 1,
) -> Generator[float, None, None]:
    yield 0.0
    if isinstance(interval, (int, float)):
        itr: Iterable[float] = itertools.repeat(float(interval))
    else:
        itr = iter(interval)
    for val in itr:  # noqa: UP028
        yield val


constant = _Wait(_constant)


def _runtime(*, value: Callable[[Any], float]) -> Generator[float, None, None]:
    ret_or_exc = yield 0.0
    while True:
        ret_or_exc = yield value(ret_or_exc)


runtime = _Wait(_runtime)


def _wait_random_exponential(
    multiplier: float = 1,
    max_value: float | None = None,
    exp_base: float = 2,
    min_value: float = 0,
) -> Generator[float, None, None]:
    yield 0.0
    n = 0
    while True:
        a = multiplier * exp_base**n
        if max_value is not None and a > max_value:
            a = max_value
        if a < min_value:
            a = min_value
        yield random.uniform(0, a)
        n += 1


wait_random_exponential = _Wait(_wait_random_exponential)


def _wait_incrementing(
    start: float = 1, increment: float = 1, max_value: float | None = None
) -> Generator[float, None, None]:
    yield 0.0
    n = 0
    while True:
        a = start + n * increment
        if max_value is not None and a > max_value:
            yield max_value
        else:
            yield a
        n += 1


wait_incrementing = _Wait(_wait_incrementing)


def _wait_chain(
    *generators: Generator[float, None, None],
) -> Generator[float, None, None]:
    yield 0.0
    for gen in generators:
        next(gen)
        val = gen.send(None)
        yield val
        while True:
            try:
                val = gen.send(None)
                yield val
            except StopIteration:
                break


wait_chain = _Wait(_wait_chain)


def _wait_exception(
    value: Callable[[Any], float],
) -> Generator[float, None, None]:
    exc = yield 0.0
    while True:
        exc = yield value(exc)


wait_exception = _Wait(_wait_exception)


def wait_random(min: float = 0, max: float = 1) -> Generator[float, None, None]:
    yield 0.0
    while True:
        yield random.uniform(min, max)


def wait_exponential_jitter(
    initial: float = 1,
    max: float = 60,
    exp_base: float = 2,
    jitter: float = 1,
) -> Generator[float, None, None]:
    yield 0.0
    n = 1
    while True:
        delay = min(initial * exp_base**n, max)
        delay += random.uniform(0, jitter)
        yield delay
        n += 1


def wait_none() -> Generator[float, None, None]:
    yield 0.0
    while True:
        yield 0.0
