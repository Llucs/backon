import backon
from backon import (
    AttemptTimeoutError,
    CircuitBreaker,
    Details,
    MetricsCollector,
    RateLimiter,
    RateLimitError,
    RetryAssertionError,
    disable_retries,
    get_metrics_collector,
    retry_if_not_exception_type,
    wait_exponential_jitter,
    wait_none,
    wait_random,
)


class TestNewExports:
    def test_all_symbols_importable(self):
        assert AttemptTimeoutError is not None
        assert RateLimiter is not None
        assert RateLimitError is not None
        assert Details is not None
        assert RetryAssertionError is not None
        assert CircuitBreaker is not None
        assert get_metrics_collector is not None
        assert retry_if_not_exception_type is not None
        assert wait_random is not None
        assert wait_none is not None
        assert wait_exponential_jitter is not None
        assert disable_retries is not None

    def test_wait_random(self):
        gen = wait_random(min=0.0, max=1.0)
        val = next(gen)
        assert isinstance(val, float)
        assert 0.0 <= val <= 1.0

    def test_wait_none(self):
        gen = wait_none()
        val = next(gen)
        assert val == 0.0

    def test_wait_exponential_jitter(self):
        gen = wait_exponential_jitter(initial=1.0, max=10.0)
        next(gen)
        val = next(gen)
        assert isinstance(val, float)
        assert val > 0.0

    def test_details_is_typed_dict(self):
        d: Details = {
            "target": lambda: None,
            "args": (),
            "kwargs": {},
            "tries": 1,
            "elapsed": 0.0,
            "wait": 0.0,
            "value": None,
        }
        assert d["tries"] == 1

    def test_retry_if_not_exception_type(self):
        cond = retry_if_not_exception_type(ValueError)
        assert callable(cond)

    def test_disable_retries_context_manager(self):
        with backon.disable_retries():
            pass

    def test_retry_assertion_error(self):
        assert issubclass(RetryAssertionError, AssertionError)

    def test_circuit_breaker_defaults(self):
        cb = CircuitBreaker()
        assert cb is not None

    def test_get_metrics_collector(self):
        mc = get_metrics_collector()
        assert isinstance(mc, MetricsCollector)

    def test_wait_random_in_backon(self):
        assert hasattr(backon, "wait_random")
        assert callable(backon.wait_random)

    def test_wait_none_in_backon(self):
        assert hasattr(backon, "wait_none")
        assert callable(backon.wait_none)

    def test_wait_exponential_jitter_in_backon(self):
        assert hasattr(backon, "wait_exponential_jitter")
        assert callable(backon.wait_exponential_jitter)

    def test_details_in_backon(self):
        assert hasattr(backon, "Details")

    def test_retry_if_not_exception_type_in_backon(self):
        assert hasattr(backon, "retry_if_not_exception_type")
        assert callable(backon.retry_if_not_exception_type)

    def test_disable_retries_in_backon(self):
        assert hasattr(backon, "disable_retries")

    def test_retry_assertion_error_in_backon(self):
        assert hasattr(backon, "RetryAssertionError")

    def test_circuit_breaker_in_backon(self):
        assert hasattr(backon, "CircuitBreaker")

    def test_get_metrics_collector_in_backon(self):
        assert hasattr(backon, "get_metrics_collector")
        assert callable(backon.get_metrics_collector)
