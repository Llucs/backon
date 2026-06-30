from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _version

from backon._common import disable, enable
from backon._conditions import (
    RetryCondition,
    Stop,
    retry_all,
    retry_always,
    retry_any,
    retry_if_exception,
    retry_if_exception_message,
    retry_if_exception_type,
    retry_if_not_result,
    retry_if_result,
    retry_never,
    stop_after_attempt,
    stop_after_delay,
    stop_all,
    stop_any,
    stop_before_delay,
    stop_never,
    stop_when_event_set,
)
from backon._context import get_attempt_number, is_retrying
from backon._decorator import on_exception, on_predicate
from backon._jitter import full_jitter, random_jitter
from backon._retry import (
    AsyncRetryingCaller,
    Retrying,
    RetryingCaller,
    retry,
    sleep_using_event,
)
from backon._state import RetryCallState, RetryError, RetryState, TryAgain
from backon._wait_gen import (
    constant,
    decay,
    expo,
    fibo,
    runtime,
    wait_chain,
    wait_exception,
    wait_incrementing,
    wait_random_exponential,
)

try:
    __version__ = _version("backon")
except _PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"


__all__ = [
    "on_predicate",
    "on_exception",
    "retry",
    "Retrying",
    "constant",
    "expo",
    "decay",
    "fibo",
    "runtime",
    "wait_random_exponential",
    "wait_incrementing",
    "wait_chain",
    "wait_exception",
    "full_jitter",
    "random_jitter",
    "disable",
    "enable",
    "is_retrying",
    "get_attempt_number",
    "sleep_using_event",
    "RetryingCaller",
    "AsyncRetryingCaller",
    "TryAgain",
    "RetryError",
    "RetryState",
    "RetryCallState",
    "Stop",
    "RetryCondition",
    "stop_after_attempt",
    "stop_after_delay",
    "stop_before_delay",
    "stop_all",
    "stop_any",
    "stop_never",
    "stop_when_event_set",
    "retry_if_exception_type",
    "retry_if_exception",
    "retry_if_exception_message",
    "retry_if_result",
    "retry_if_not_result",
    "retry_all",
    "retry_any",
    "retry_always",
    "retry_never",
]
