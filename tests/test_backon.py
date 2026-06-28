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
            "sleep_using_event",
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
        }
        assert set(backon.__all__) == expected
