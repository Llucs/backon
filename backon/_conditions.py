from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from typing import Any

from backon._state import RetryState


class Stop:
    def __call__(self, state: RetryState) -> bool:
        raise NotImplementedError


class stop_after_attempt(Stop):
    def __init__(self, max_attempts: int) -> None:
        self.max_attempts = max_attempts

    def __call__(self, state: RetryState) -> bool:
        return state.tries >= self.max_attempts


class stop_after_delay(Stop):
    def __init__(self, max_delay: float) -> None:
        self.max_delay = max_delay

    def __call__(self, state: RetryState) -> bool:
        return state.elapsed >= self.max_delay


class stop_before_delay(Stop):
    def __init__(self, max_delay: float) -> None:
        self.max_delay = max_delay

    def __call__(self, state: RetryState) -> bool:
        elapsed = state.elapsed
        wait = getattr(state.outcome, "wait", 0.0) if state.outcome else 0.0
        return elapsed + wait >= self.max_delay


class stop_all(Stop):
    def __init__(self, *stops: Stop) -> None:
        self.stops = stops

    def __call__(self, state: RetryState) -> bool:
        return all(s(state) for s in self.stops)


class stop_any(Stop):
    def __init__(self, *stops: Stop) -> None:
        self.stops = stops

    def __call__(self, state: RetryState) -> bool:
        return any(s(state) for s in self.stops)


class stop_never(Stop):
    def __call__(self, state: RetryState) -> bool:
        return False


class stop_when_event_set(Stop):
    def __init__(self, event: threading.Event) -> None:
        self.event = event

    def __call__(self, state: RetryState) -> bool:
        return self.event.is_set()


class RetryCondition:
    def __call__(self, state: RetryState) -> bool:
        raise NotImplementedError


class retry_if_exception_type(RetryCondition):
    def __init__(self, exc_types: type[Exception] | Sequence[type[Exception]]) -> None:
        if isinstance(exc_types, type):
            exc_types = (exc_types,)
        self.exc_types = tuple(exc_types)

    def __call__(self, state: RetryState) -> bool:
        if state.outcome is None:
            return False
        exc = state.outcome.exception
        return exc is not None and isinstance(exc, self.exc_types)


class retry_if_exception(RetryCondition):
    def __init__(self, predicate: Callable[[BaseException], bool]) -> None:
        self.predicate = predicate

    def __call__(self, state: RetryState) -> bool:
        if state.outcome is None:
            return False
        exc = state.outcome.exception
        return exc is not None and self.predicate(exc)


class retry_if_exception_message(RetryCondition):
    def __init__(self, message: str, match: str | None = None) -> None:
        self.message = message
        self.match = match

    def __call__(self, state: RetryState) -> bool:
        if state.outcome is None:
            return False
        exc = state.outcome.exception
        if exc is None:
            return False
        msg = str(exc)
        if self.match == "re":
            import re

            return bool(re.search(self.message, msg))
        return self.message in msg


class retry_if_result(RetryCondition):
    def __init__(self, predicate: Callable[[Any], bool]) -> None:
        self.predicate = predicate

    def __call__(self, state: RetryState) -> bool:
        if state.outcome is None:
            return False
        if state.outcome.exception is not None:
            return False
        return self.predicate(state.outcome.value)


class retry_if_not_result(RetryCondition):
    def __init__(self, predicate: Callable[[Any], bool]) -> None:
        self.predicate = predicate

    def __call__(self, state: RetryState) -> bool:
        if state.outcome is None:
            return False
        if state.outcome.exception is not None:
            return False
        return not self.predicate(state.outcome.value)


class retry_all(RetryCondition):
    def __init__(self, *conditions: RetryCondition) -> None:
        self.conditions = conditions

    def __call__(self, state: RetryState) -> bool:
        return all(c(state) for c in self.conditions)


class retry_any(RetryCondition):
    def __init__(self, *conditions: RetryCondition) -> None:
        self.conditions = conditions

    def __call__(self, state: RetryState) -> bool:
        return any(c(state) for c in self.conditions)


class retry_always(RetryCondition):
    def __call__(self, state: RetryState) -> bool:
        return True


class retry_never(RetryCondition):
    def __call__(self, state: RetryState) -> bool:
        return False
