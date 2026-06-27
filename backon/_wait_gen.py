import itertools
import math
from typing import Any, Callable, Generator, Iterable, Optional, Sequence, Union


def expo(
    base: float = 2, factor: float = 1, max_value: Optional[float] = None
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
    initial_value: float = 1, decay_factor: float = 1, min_value: Optional[float] = None
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


def fibo(max_value: Optional[int] = None) -> Generator[int, None, None]:
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
    interval: Union[int, float, Sequence[float]] = 1,
) -> Generator[float, None, None]:
    yield 0.0  # prime
    if isinstance(interval, (int, float)):
        itr: Iterable[float] = itertools.repeat(float(interval))
    else:
        itr = iter(interval)

    for val in itr:
        yield val


def runtime(*, value: Callable[[Any], float]) -> Generator[float, None, None]:
    ret_or_exc = yield 0.0
    while True:
        ret_or_exc = yield value(ret_or_exc)
