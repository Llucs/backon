from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Iterator, Sequence
from typing import Any


class _Wait:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs

    def next(self, send_value=None) -> float:
        raise NotImplementedError

    def __call__(self, *args: Any, **kwargs: Any) -> _Wait:
        merged = {**self._kwargs, **kwargs}
        new_args = args if args else self._args
        return self.__class__(*new_args, **merged)

    def __add__(self, other: _Wait) -> _CombinedWait:
        if isinstance(other, _CombinedWait):
            return _CombinedWait(self, *other._waits)
        return _CombinedWait(self, other)

    def __radd__(self, other: _Wait) -> _CombinedWait:
        return _CombinedWait(other, self)


class _CombinedWait(_Wait):
    def __init__(self, *waits: _Wait) -> None:
        super().__init__()
        self._waits = tuple(waits)

    def next(self, send_value=None) -> float:
        return sum(w.next(send_value) for w in self._waits)

    def __call__(self, **kwargs: Any) -> _CombinedWait:
        return _CombinedWait(*(w(**kwargs) for w in self._waits))

    def __add__(self, other: _Wait) -> _CombinedWait:
        if isinstance(other, _CombinedWait):
            return _CombinedWait(*self._waits, *other._waits)
        return _CombinedWait(*self._waits, other)


class _Expo(_Wait):
    def __init__(
        self,
        base: float = 2,
        factor: float = 1,
        max_value: float | None = None,
    ) -> None:
        super().__init__(base=base, factor=factor, max_value=max_value)
        self._base = base
        self._factor = factor
        self._max_value = max_value
        self._n = 0

    def next(self, send_value=None) -> float:
        a = self._factor * self._base**self._n
        if self._max_value is None or a < self._max_value:
            self._n += 1
            return a
        return self._max_value


expo = _Expo()


class _Decay(_Wait):
    def __init__(
        self,
        initial_value: float = 1,
        decay_factor: float = 1,
        min_value: float | None = None,
    ) -> None:
        super().__init__(
            initial_value=initial_value,
            decay_factor=decay_factor,
            min_value=min_value,
        )
        self._initial_value = initial_value
        self._decay_factor = decay_factor
        self._min_value = min_value
        self._t = 0

    def next(self, send_value=None) -> float:
        a = self._initial_value * float(math.e ** (-self._t * self._decay_factor))
        if self._min_value is None or a > self._min_value:
            self._t += 1
            return a
        return self._min_value


decay = _Decay()


class _Fibo(_Wait):
    def __init__(self, max_value: int | None = None) -> None:
        super().__init__(max_value=max_value)
        self._max_value = max_value
        self._a = 1
        self._b = 1

    def next(self, send_value=None) -> float:
        if self._max_value is None or self._a < self._max_value:
            result = self._a
            self._a, self._b = self._b, self._a + self._b
            return float(result)
        return float(self._max_value)


fibo = _Fibo()


class _Constant(_Wait):
    def __init__(self, interval: int | float | Sequence[float] = 1) -> None:
        super().__init__(interval=interval)
        self._itr: Iterator[float]
        if isinstance(interval, (int, float)):
            self._itr = itertools.repeat(float(interval))
        else:
            self._itr = iter(interval)

    def next(self, send_value=None) -> float:
        return next(self._itr)


constant = _Constant()


class _Runtime(_Wait):
    def __init__(self, *, value: Callable[[Any], float]) -> None:
        super().__init__(value=value)
        self._value = value

    def next(self, send_value=None) -> float:
        return self._value(send_value)


runtime = _Runtime(value=lambda x: x)


class _WaitRandomExponential(_Wait):
    def __init__(
        self,
        multiplier: float = 1,
        max_value: float | None = None,
        exp_base: float = 2,
        min_value: float = 0,
    ) -> None:
        super().__init__(
            multiplier=multiplier,
            max_value=max_value,
            exp_base=exp_base,
            min_value=min_value,
        )
        self._multiplier = multiplier
        self._max_value = max_value
        self._exp_base = exp_base
        self._min_value = min_value
        self._n = 0

    def next(self, send_value=None) -> float:
        a = self._multiplier * self._exp_base**self._n
        if self._max_value is not None and a > self._max_value:
            a = self._max_value
        if a < self._min_value:
            a = self._min_value
        self._n += 1
        return random.uniform(0, a)


wait_random_exponential = _WaitRandomExponential()


class _WaitIncrementing(_Wait):
    def __init__(
        self,
        start: float = 1,
        increment: float = 1,
        max_value: float | None = None,
    ) -> None:
        super().__init__(start=start, increment=increment, max_value=max_value)
        self._start = start
        self._increment = increment
        self._max_value = max_value
        self._n = 0

    def next(self, send_value=None) -> float:
        a = self._start + self._n * self._increment
        self._n += 1
        if self._max_value is not None and a > self._max_value:
            return self._max_value
        return a


wait_incrementing = _WaitIncrementing()


class _WaitChain(_Wait):
    def __init__(self, *waits: _Wait) -> None:
        super().__init__()
        self._waits = list(waits)
        self._idx = 0

    def __call__(self, **kwargs: Any) -> _WaitChain:
        return _WaitChain(*(w(**kwargs) for w in self._waits))

    def next(self, send_value=None) -> float:
        if not self._waits:
            return 0.0
        w = self._waits[self._idx]
        self._idx = (self._idx + 1) % len(self._waits)
        return w.next(send_value)


def wait_chain(*waits: _Wait) -> _WaitChain:
    return _WaitChain(*waits)


def wait_combine(*waits: _Wait) -> _CombinedWait:
    return _CombinedWait(*waits)


class _WaitException(_Wait):
    def __init__(self, *, value: Callable[[Any], float]) -> None:
        super().__init__(value=value)
        self._value = value

    def next(self, send_value=None) -> float:
        return self._value(send_value)


wait_exception = _WaitException(value=lambda x: x)


class _WaitRandom(_Wait):
    def __init__(self, min: float = 0, max: float = 1) -> None:
        super().__init__(min=min, max=max)
        self._min = min
        self._max = max

    def next(self, send_value=None) -> float:
        return random.uniform(self._min, self._max)


wait_random = _WaitRandom()


class _WaitExponentialJitter(_Wait):
    def __init__(
        self,
        initial: float = 1,
        max: float = 60,
        exp_base: float = 2,
        jitter: float = 1,
    ) -> None:
        super().__init__(initial=initial, max=max, exp_base=exp_base, jitter=jitter)
        self._initial = initial
        self._max = max
        self._exp_base = exp_base
        self._jitter = jitter
        self._n = 1

    def next(self, send_value=None) -> float:
        delay = min(self._initial * self._exp_base**self._n, self._max)
        delay += random.uniform(0, self._jitter)
        self._n += 1
        return delay


wait_exponential_jitter = _WaitExponentialJitter()


class _WaitNone(_Wait):
    def next(self, send_value=None) -> float:
        return 0.0


wait_none = _WaitNone()
