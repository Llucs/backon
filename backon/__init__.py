from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _version

from backon._circuit_breaker import BreakerRetrying, CircuitBreaker, CircuitOpenError
from backon._common import disable, enable
from backon._conditions import (
    RetryCondition,
    Stop,
    retry_all,
    retry_always,
    retry_any,
    retry_if_exception,
    retry_if_exception_cause_type,
    retry_if_exception_message,
    retry_if_exception_type,
    retry_if_not_exception_message,
    retry_if_not_exception_type,
    retry_if_not_result,
    retry_if_result,
    retry_never,
    retry_unless_exception_type,
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
from backon._hedging import HedgeError, HedgingRetrying, hedge, on_hedge
from backon._jitter import full_jitter, random_jitter
from backon._rate_limiter import RateLimiter, RateLimitError
from backon._retry import (
    AsyncRetryingCaller,
    Retrying,
    RetryingCaller,
    retry,
    sleep_using_event,
)
from backon._state import (
    AttemptTimeoutError,
    RetryCallState,
    RetryError,
    RetryState,
    TryAgain,
)
from backon._testing import (
    RetryAssertionError,
    assert_not_retried,
    assert_retried,
    disable_retries,
    enable_retries,
    limit_retries,
    remove_backoff,
    test_config,
)
from backon._wait_gen import (
    constant,
    decay,
    expo,
    fibo,
    runtime,
    wait_chain,
    wait_combine,
    wait_exception,
    wait_exponential_jitter,
    wait_incrementing,
    wait_none,
    wait_random,
    wait_random_exponential,
)
from backon.types import Details

try:
    __version__ = _version("backon")
except _PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"


__all__ = [
    "AsyncRetryingCaller",
    "AttemptTimeoutError",
    "BreakerRetrying",
    "CircuitBreaker",
    "CircuitOpenError",
    "Details",
    "HedgeError",
    "HedgingRetrying",
    "RateLimitError",
    "RateLimiter",
    "RetryAssertionError",
    "RetryCallState",
    "RetryCondition",
    "RetryError",
    "RetryState",
    "Retrying",
    "RetryingCaller",
    "Stop",
    "TryAgain",
    "assert_not_retried",
    "assert_retried",
    "constant",
    "decay",
    "disable",
    "disable_retries",
    "enable",
    "enable_retries",
    "expo",
    "fibo",
    "full_jitter",
    "get_attempt_number",
    "hedge",
    "is_retrying",
    "limit_retries",
    "on_exception",
    "on_hedge",
    "on_predicate",
    "random_jitter",
    "remove_backoff",
    "retry",
    "retry_all",
    "retry_always",
    "retry_any",
    "retry_if_exception",
    "retry_if_exception_cause_type",
    "retry_if_exception_message",
    "retry_if_exception_type",
    "retry_if_not_exception_message",
    "retry_if_not_exception_type",
    "retry_if_not_result",
    "retry_if_result",
    "retry_never",
    "retry_unless_exception_type",
    "runtime",
    "sleep_using_event",
    "stop_after_attempt",
    "stop_after_delay",
    "stop_all",
    "stop_any",
    "stop_before_delay",
    "stop_never",
    "stop_when_event_set",
    "test_config",
    "wait_chain",
    "wait_combine",
    "wait_exception",
    "wait_exponential_jitter",
    "wait_incrementing",
    "wait_none",
    "wait_random",
    "wait_random_exponential",
]
