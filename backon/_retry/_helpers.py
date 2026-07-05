from __future__ import annotations

from datetime import timedelta

from backon._conditions import (
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    stop_any,
    stop_never,
)


def _to_seconds(value: float | int | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    return float(value)


def _make_default_stop(max_tries, max_time):
    stops = []
    if max_tries is not None:
        stops.append(stop_after_attempt(max_tries))
    if max_time is not None:
        stops.append(stop_after_delay(_to_seconds(max_time)))
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
                    result = giveup(state.outcome.exception)
                    if isinstance(result, bool):
                        return not result
                    if isinstance(result, (int, float)):
                        return float(result)
                    return True
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
