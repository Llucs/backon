import contextlib
import threading
import time

import pytest

from backon._circuit_breaker import (
    BreakerRetrying,
    CircuitBreaker,
    CircuitBreakerState,
    CircuitOpenError,
)
from backon._wait_gen import constant


class TestCircuitBreakerState:
    def test_enum_values(self):
        assert CircuitBreakerState.CLOSED.value == "CLOSED"
        assert CircuitBreakerState.OPEN.value == "OPEN"
        assert CircuitBreakerState.HALF_OPEN.value == "HALF_OPEN"

    def test_enum_identity(self):
        assert CircuitBreakerState.CLOSED is CircuitBreakerState.CLOSED
        assert CircuitBreakerState.OPEN is CircuitBreakerState.OPEN
        assert CircuitBreakerState.HALF_OPEN is CircuitBreakerState.HALF_OPEN


class TestCircuitOpenError:
    def test_is_exception_subclass(self):
        assert issubclass(CircuitOpenError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(CircuitOpenError):
            raise CircuitOpenError()

    def test_can_be_raised_with_message(self):
        with pytest.raises(CircuitOpenError):
            raise CircuitOpenError("custom message")


class TestCircuitBreakerBasics:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_initial_failure_count_zero(self):
        cb = CircuitBreaker()
        assert cb.failure_count == 0

    def test_initial_success_count_zero(self):
        cb = CircuitBreaker()
        assert cb.success_count == 0

    def test_default_name_empty(self):
        cb = CircuitBreaker()
        assert cb.name == ""

    def test_custom_name(self):
        cb = CircuitBreaker(name="my_breaker")
        assert cb.name == "my_breaker"

    def test_custom_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=10)
        assert cb._failure_threshold == 10

    def test_custom_recovery_timeout(self):
        cb = CircuitBreaker(recovery_timeout=30.0)
        assert cb._recovery_timeout == 30.0

    def test_custom_half_open_max_calls(self):
        cb = CircuitBreaker(half_open_max_calls=3)
        assert cb._half_open_max_calls == 3


class TestCircuitBreakerTransitions:
    def test_closed_to_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_open_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        cb._recovery_timeout = 0.0
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        cb._recovery_timeout = 0.0
        assert cb.state == CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        cb._state = CircuitBreakerState.HALF_OPEN
        cb._last_failure_time = 0.0
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_record_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        cb.record_success()
        assert cb.failure_count == 0

    def test_record_failure_increments_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        assert cb.failure_count == 1

        cb.record_failure()
        assert cb.failure_count == 2

    def test_record_failure_updates_last_failure_time(self):
        cb = CircuitBreaker(failure_threshold=5)
        before = time.monotonic()
        cb.record_failure()
        after = time.monotonic()
        assert before <= cb._last_failure_time <= after


class TestCircuitBreakerCall:
    def test_successful_call_returns_result(self):
        cb = CircuitBreaker(failure_threshold=5)
        result = cb.call(lambda: 42)
        assert result == 42

    def test_successful_call_via_call_operator(self):
        cb = CircuitBreaker(failure_threshold=5)
        result = cb(lambda: 42)
        assert result == 42

    def test_call_with_arguments(self):
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.call(lambda x, y: x + y, 40, 2)
        assert result == 42

    def test_successful_call_records_success(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.success_count == 0
        cb.call(lambda: 42)
        assert cb.success_count == 1

    def test_failed_call_reraises(self):
        cb = CircuitBreaker(failure_threshold=3)

        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            cb.call(fail)

    def test_failed_call_records_failure(self):
        cb = CircuitBreaker(failure_threshold=3)

        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            cb.call(fail)

        assert cb.failure_count == 1

    def test_consecutive_failures_open_circuit(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)

        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            cb.call(fail)
        assert cb.state == CircuitBreakerState.CLOSED

        with pytest.raises(ValueError):
            cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

    def test_open_circuit_blocks_call(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "should not reach")

    def test_open_circuit_blocks_call_operator(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()

        with pytest.raises(CircuitOpenError):
            cb(lambda: "should not reach")

    def test_recovery_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        cb._recovery_timeout = 0.0
        assert cb.state == CircuitBreakerState.HALF_OPEN
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_success_count_resets_on_failure(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.call(lambda: 1)
        cb.call(lambda: 2)
        assert cb.success_count == 2

        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            cb.call(fail)

        assert cb.success_count == 0

    def test_half_open_with_max_calls(self):
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=60.0,
            half_open_max_calls=2,
        )
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        cb._recovery_timeout = 0.0
        assert cb.state == CircuitBreakerState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerContextManager:
    def test_sync_context_manager(self):
        cb = CircuitBreaker(failure_threshold=3)
        with cb:
            result = cb.call(lambda: 42)
        assert result == 42

    def test_sync_context_manager_preserves_state(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        with cb, pytest.raises(CircuitOpenError):
            cb.call(lambda: 42)

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        cb = CircuitBreaker(failure_threshold=3)
        async with cb:
            result = cb.call(lambda: 42)
        assert result == 42


class TestCircuitBreakerAsync:
    @pytest.mark.asyncio
    async def test_async_successful_call(self):
        cb = CircuitBreaker(failure_threshold=3)

        async def work():
            return 42

        result = await cb.async_call(work)
        assert result == 42
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_failed_call(self):
        cb = CircuitBreaker(failure_threshold=2)

        async def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.async_call(fail)

        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_async_open_blocks(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        async def work():
            return 42

        with pytest.raises(CircuitOpenError):
            await cb.async_call(work)

    @pytest.mark.asyncio
    async def test_async_recovery_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

        async def work():
            return "recovered"

        cb._recovery_timeout = 0.0
        assert cb.state == CircuitBreakerState.HALF_OPEN
        result = await cb.async_call(work)
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerThreadSafety:
    def test_concurrent_successful_calls(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.0)
        errors = []

        def worker():
            for _ in range(20):
                try:
                    cb.call(lambda: 42)
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_failures_open_circuit(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.0)
        results = []
        lock = threading.Lock()

        def flaky():
            raise ValueError("fail")

        def worker():
            for _ in range(5):
                try:
                    cb.call(flaky)
                except (ValueError, CircuitOpenError):
                    pass
                except Exception as e:
                    with lock:
                        results.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 0

    def test_thread_safety_with_mixed_outcomes(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.01)
        call_counter = 0
        counter_lock = threading.Lock()

        def conditional():
            with counter_lock:
                nonlocal call_counter
                call_counter += 1
                if call_counter <= 3:
                    raise ValueError("fail")
            return "ok"

        def worker():
            for _ in range(10):
                with contextlib.suppress(ValueError, CircuitOpenError):
                    cb.call(conditional)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()


class TestBreakerRetrying:
    def test_breaker_open_raises_immediately(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()

        br = BreakerRetrying(
            constant, breaker=cb, max_tries=3, jitter=None, interval=0.01
        )

        with pytest.raises(CircuitOpenError):
            br.call(lambda: "should not run")

    def test_retry_then_succeed(self):
        cb = CircuitBreaker(failure_threshold=3)
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        br = BreakerRetrying(
            constant,
            breaker=cb,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        result = br.call(flaky)

        assert result == "ok"
        assert len(calls) == 3
        assert cb.failure_count == 0

    def test_retry_exhausted_records_failure(self):
        cb = CircuitBreaker(failure_threshold=3)
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        br = BreakerRetrying(
            constant,
            breaker=cb,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
        )

        with pytest.raises(ValueError):
            br.call(flaky)

        assert len(calls) == 2
        assert cb.failure_count == 1

    def test_multiple_failures_open_breaker(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        br = BreakerRetrying(
            constant,
            breaker=cb,
            exception=ValueError,
            max_tries=1,
            jitter=None,
            interval=0.01,
        )

        with pytest.raises(ValueError):
            br.call(flaky)
        assert cb.failure_count == 1
        assert cb.state == CircuitBreakerState.CLOSED

        with pytest.raises(ValueError):
            br.call(flaky)
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN

    def test_successful_call_records_success_on_breaker(self):
        cb = CircuitBreaker(failure_threshold=3)

        br = BreakerRetrying(
            constant, breaker=cb, max_tries=1, jitter=None, interval=0.01
        )
        br.call(lambda: 42)

        assert cb.failure_count == 0
        assert cb.success_count == 1

    def test_default_breaker_auto_created(self):
        br = BreakerRetrying(constant, max_tries=1, jitter=None, interval=0.01)
        assert br.breaker is not None
        assert br.breaker.state == CircuitBreakerState.CLOSED

    def test_breaker_property(self):
        cb = CircuitBreaker()
        br = BreakerRetrying(
            constant,
            breaker=cb,
            max_tries=1,
            jitter=None,
            interval=0.01,
        )
        assert br.breaker is cb

    @pytest.mark.asyncio
    async def test_async_breaker_open_raises_immediately(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()

        br = BreakerRetrying(
            constant, breaker=cb, max_tries=3, jitter=None, interval=0.01
        )

        with pytest.raises(CircuitOpenError):
            await br.async_call(lambda: "should not run")

    @pytest.mark.asyncio
    async def test_async_retry_then_succeed(self):
        cb = CircuitBreaker(failure_threshold=3)
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        br = BreakerRetrying(
            constant,
            breaker=cb,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        result = await br.async_call(flaky)

        assert result == "ok"
        assert len(calls) == 3
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_async_retry_exhausted_records_failure(self):
        cb = CircuitBreaker(failure_threshold=3)
        calls = []

        async def flaky():
            calls.append(1)
            raise ValueError("fail")

        br = BreakerRetrying(
            constant,
            breaker=cb,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
        )

        with pytest.raises(ValueError):
            await br.async_call(flaky)

        assert len(calls) == 2
        assert cb.failure_count == 1
