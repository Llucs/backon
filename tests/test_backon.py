import backon
from backon.types import Details


class TestImports:
    def test_on_predicate(self):
        assert hasattr(backon, "on_predicate")

    def test_on_exception(self):
        assert hasattr(backon, "on_exception")

    def test_wait_generators(self):
        assert hasattr(backon, "expo")
        assert hasattr(backon, "fibo")
        assert hasattr(backon, "constant")
        assert hasattr(backon, "runtime")
        assert hasattr(backon, "decay")

    def test_jitter(self):
        assert hasattr(backon, "full_jitter")
        assert hasattr(backon, "random_jitter")

    def test_version(self):
        assert isinstance(backon.__version__, str)
        assert len(backon.__version__) > 0

    def test_details_importable(self):
        assert Details is not None

    def test_all_exports(self):
        expected = {
            "assert_not_retried",
            "assert_retried",
            "AsyncRetryingCaller",
            "AttemptTimeoutError",
            "BreakerRetrying",
            "CircuitBreaker",
            "CircuitOpenError",
            "constant",
            "decay",
            "Details",
            "disable",
            "disable_retries",
            "enable",
            "enable_retries",
            "expo",
            "fibo",
            "full_jitter",
            "get_attempt_number",
            "hedge",
            "HedgeError",
            "HedgingRetrying",
            "is_retrying",
            "limit_retries",
            "on_exception",
            "on_hedge",
            "on_predicate",
            "random_jitter",
            "RateLimiter",
            "RateLimitError",
            "remove_backoff",
            "retry",
            "RetryAssertionError",
            "RetryCallState",
            "RetryCondition",
            "RetryError",
            "Retrying",
            "RetryingCaller",
            "RetryState",
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
            "Stop",
            "stop_after_attempt",
            "stop_after_delay",
            "stop_all",
            "stop_any",
            "stop_before_delay",
            "stop_never",
            "stop_when_event_set",
            "test_config",
            "TryAgain",
            "wait_chain",
            "wait_combine",
            "wait_exception",
            "wait_exponential_jitter",
            "wait_incrementing",
            "wait_none",
            "wait_random",
            "wait_random_exponential",
        }
        assert set(backon.__all__) == expected
