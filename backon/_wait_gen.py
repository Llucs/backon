import itertools
import math
import random
from collections.abc import Callable, Generator, Iterable, Sequence
from typing import Any


def expo(
    base: float = 2, factor: float = 1, max_value: float | None = None
) -> Generator[float, Any, None]:
    yield 0.0  # prime
    n = 0
    while True:
        a = factor * base**n
        if max_value is None or a < max_value:
            yield a
            n += 1
        else:
            yield max_value


def decay(
    initial_value: float = 1, decay_factor: float = 1, min_value: float | None = None
) -> Generator[float, Any, None]:
    yield 0.0  # prime
    t = 0
    while True:
        a = initial_value * math.e ** (-t * decay_factor)
        if min_value is None or a > min_value:
            yield a
            t += 1
        else:
            yield min_value


def fibo(max_value: int | None = None) -> Generator[int, None, None]:
    yield 0  # prime
    a = 1
    b = 1
    while True:
        if max_value is None or a < max_value:
            yield a
            a, b = b, a + b
        else:
            yield max_value


def constant(
    interval: int | float | Sequence[float] = 1,
) -> Generator[float, None, None]:
    yield 0.0  # prime
    if isinstance(interval, (int, float)):
        itr: Iterable[float] = itertools.repeat(float(interval))
    else:
        itr = iter(interval)

    for val in itr:  # noqa: UP028
        yield val


def runtime(*, value: Callable[[Any], float]) -> Generator[float, None, None]:
    ret_or_exc = yield 0.0
    while True:
        ret_or_exc = yield value(ret_or_exc)


def wait_random_exponential(
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


def wait_incrementing(
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


def wait_chain(
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


def wait_exception(
    value: Callable[[Any], float],
) -> Generator[float, None, None]:
    exc = yield 0.0
    while True:
        exc = yield value(exc)
