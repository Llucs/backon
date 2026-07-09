import asyncio
import threading
import time

import pytest

import backon
from backon._circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitOpenError,
)
from backon._common import _apply_test_overrides
from backon._conditions import (
    RetryCondition,
    retry_any,
    retry_if_exception,
    retry_if_exception_type,
)
from backon._rate_limiter import RateLimiter
from backon._retry._classes import Retrying, RetryingCaller, _RetryAttempt
from backon._retry._decide import _decide_outcome, _RetryAction
from backon._retry._helpers import _make_default_condition, _make_default_stop
from backon._retry._inner import _retry_async_inner, _retry_sync_inner
from backon._state import (
    Attempt,
    AttemptTimeoutError,
    RetryCallState,
    RetryState,
    TryAgain,
)
from backon._testing import test_config as _test_config
from backon._wait_gen import (
    _CombinedWait,
    _Wait,
    _WaitChain,
    _WaitRandomExponential,
    constant,
)

_KW = dict(jitter=None, interval=0.01)


class _FiniteWait(_Wait):
    def __init__(self, **kwargs):
        self._calls = 0

    def next(self, send_value=None):
        self._calls += 1
        if self._calls >= 2:
            raise StopIteration
        return 0.01


finite_wait = _FiniteWait


class TestCircuitBreakerHalfOpenMaxCalls:
    def test_half_open_max_calls_exceeded_sync(self):
        cb = CircuitBreaker(
            failure_threshold=1, recovery_timeout=0, half_open_max_calls=1
        )
        cb.record_failure()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        def slow_fn():
            time.sleep(0.05)
            return 42

        results = []
        errors = []

        def call_breaker():
            try:
                results.append(cb.call(slow_fn))
            except CircuitOpenError as e:
                errors.append(e)

        t1 = threading.Thread(target=call_breaker)
        t2 = threading.Thread(target=call_breaker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 1
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_half_open_max_calls_exceeded_async(self):
        cb = CircuitBreaker(
            failure_threshold=1, recovery_timeout=0, half_open_max_calls=1
        )
        cb.record_failure()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        async def slow_fn():
            await asyncio.sleep(0.05)
            return 42

        async def call_breaker():
            try:
                return await cb.async_call(slow_fn)
            except CircuitOpenError:
                return None

        results = await asyncio.gather(call_breaker(), call_breaker())
        assert len([r for r in results if r == 42]) == 1
        assert len([r for r in results if r is None]) == 1


class TestApplyTestOverrides:
    def test_apply_test_overrides_with_max_retries(self):
        with _test_config(max_retries=2):
            mt, mtime = _apply_test_overrides(max_tries=10, max_time=30.0)
            assert mt == 2
            assert mtime == 30.0

    def test_apply_test_overrides_none(self):
        with _test_config(max_retries=None):
            mt, mtime = _apply_test_overrides(max_tries=5, max_time=None)
            assert mt == 5
            assert mtime is None


class TestRetryIfExceptionTypeOutcomeNone:
    def test_outcome_none_returns_false(self):
        c = retry_if_exception_type(ValueError)
        state = RetryState()
        assert c(state) is False


class TestRetryIfExceptionFloatResult:
    def test_exc_none_returns_false(self):
        c = retry_if_exception(lambda e: 0.5)
        state = RetryState()
        state.outcome = Attempt(exception=None)
        result = c(state)
        assert result is False

    def test_predicate_returns_float(self):
        c = retry_if_exception(lambda e: 0.05)
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        result = c(state)
        assert result == 0.05


class TestRetryAnyFloatResult:
    def test_float_from_condition(self):
        def float_condition(state):
            if state.outcome and state.outcome.exception:
                return 0.05
            return False

        c = retry_any(retry_if_exception_type(ValueError), float_condition)
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        result = c(state)
        assert result is True

    def test_float_from_condition_first(self):
        def float_condition(state):
            if state.outcome and state.outcome.exception:
                return 0.05
            return False

        c = retry_any(float_condition, retry_if_exception_type(ValueError))
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        result = c(state)
        assert result == 0.05


class TestDecoratorGiveupTruthyNonBool:
    def test_on_exception_giveup_truthy_string(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            giveup=lambda e: "retry",
        )
        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        assert flaky() == "ok"
        assert len(calls) == 3


class TestMakeDefaultConditionEdgeCases:
    def test_giveup_returns_truthy_non_bool(self):
        condition = _make_default_condition(
            exception=ValueError,
            giveup=lambda e: "retry",
            predicate=lambda x: False,
        )
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        assert condition(state) is True

    def test_predicate_condition_outcome_none(self):
        condition = _make_default_condition(
            exception=None, giveup=None, predicate=lambda x: x is None
        )
        state = RetryState()
        assert condition(state) is False

    def test_predicate_condition_with_exception(self):
        condition = _make_default_condition(
            exception=None, giveup=None, predicate=lambda x: x is None
        )
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        assert condition(state) is False


class TestDecideOutcomeEdgeCases:
    def test_attempt_timeout_stop_iteration(self):
        state = RetryState(target=lambda: 42)
        state.tries = 1
        state.elapsed = 0.1
        state.outcome = Attempt(exception=AttemptTimeoutError(), tries=1)
        call_state = RetryCallState()
        stop = _make_default_stop(max_tries=10, max_time=None)
        condition = _make_default_condition(
            exception=ValueError, giveup=None, predicate=lambda x: False
        )
        wait = _FiniteWait()
        wait.next()
        action, seconds, details, use_cb, suppress = _decide_outcome(
            state,
            call_state,
            wait,
            condition,
            stop,
            jitter=None,
            max_time=None,
            exc=AttemptTimeoutError(),
            ret=None,
        )
        assert action == _RetryAction.GIVEUP

    def test_exception_stop_iteration(self):
        state = RetryState(target=lambda: 42)
        state.tries = 1
        state.elapsed = 0.1
        state.outcome = Attempt(exception=ValueError("fail"), tries=1)
        call_state = RetryCallState()
        condition = _make_default_condition(
            exception=ValueError, giveup=None, predicate=lambda x: False
        )
        stop = _make_default_stop(max_tries=10, max_time=None)
        wait = _FiniteWait()
        wait.next()
        action, seconds, details, use_cb, suppress = _decide_outcome(
            state,
            call_state,
            wait,
            condition,
            stop,
            jitter=None,
            max_time=None,
            exc=ValueError("fail"),
            ret=None,
        )
        assert action == _RetryAction.GIVEUP

    def test_success_custom_wait_with_stop(self):
        state = RetryState(target=lambda: 42)
        state.tries = 3
        state.elapsed = 0.5
        state.outcome = Attempt(value=42, tries=3)
        call_state = RetryCallState()

        def custom_condition(s):
            return 0.05

        condition = cast_condition(custom_condition)
        stop = _make_default_stop(max_tries=2, max_time=None)
        wait = constant(interval=0.01)
        wait.next()
        action, seconds, details, use_cb, suppress = _decide_outcome(
            state,
            call_state,
            wait,
            condition,
            stop,
            jitter=None,
            max_time=None,
            exc=None,
            ret=42,
        )
        assert action == _RetryAction.GIVEUP

    def test_success_condition_true_stop_iteration(self):
        state = RetryState(target=lambda: 42)
        state.tries = 1
        state.elapsed = 0.1
        state.outcome = Attempt(value=42, tries=1)
        call_state = RetryCallState()
        condition = _make_default_condition(
            exception=None, giveup=None, predicate=lambda x: True
        )
        stop = _make_default_stop(max_tries=10, max_time=None)
        wait = _FiniteWait()
        wait.next()
        action, seconds, details, use_cb, suppress = _decide_outcome(
            state,
            call_state,
            wait,
            condition,
            stop,
            jitter=None,
            max_time=None,
            exc=None,
            ret=42,
        )
        assert action == _RetryAction.GIVEUP


def cast_condition(fn):
    class _C(RetryCondition):
        def __call__(self, state):
            return fn(state)

    return _C()


class TestRetryInnerDisabled:
    def test_sync_disabled(self):
        def target():
            return 42

        backon.disable()
        try:
            result = _retry_sync_inner(target, constant, jitter=None)
            assert result == 42
        finally:
            backon.enable()

    def test_sync_wait_gen_kwargs_none(self):
        calls = []

        def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = _retry_sync_inner(
            target,
            constant,
            condition=backon.retry_if_exception_type(ValueError),
            max_tries=3,
            jitter=None,
            sleep=lambda s: None,
            wait_gen_kwargs=None,
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_disabled(self):
        async def target():
            return 42

        backon.disable()
        try:
            result = await _retry_async_inner(target, constant, jitter=None)
            assert result == 42
        finally:
            backon.enable()

    @pytest.mark.asyncio
    async def test_async_wait_gen_kwargs_none(self):
        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = await _retry_async_inner(
            target,
            constant,
            condition=backon.retry_if_exception_type(ValueError),
            max_tries=3,
            jitter=None,
            wait_gen_kwargs=None,
        )
        assert result == "ok"


class TestRetryApiDisabledAsync:
    @pytest.mark.asyncio
    async def test_retry_async_disabled(self):
        from backon._retry._api import _retry_async

        async def target():
            return 42

        backon.disable()
        try:
            result = await _retry_async(
                target,
                constant,
                jitter=None,
                raise_on_giveup=False,
            )
            assert result == 42
        finally:
            backon.enable()


class TestRetryLoopsRateLimit:
    def test_rate_limit_sync(self):
        calls = []

        def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        rl = RateLimiter(max_calls=1, period=0.5)
        rl.acquire()

        result = backon.retry(
            target,
            backon.constant,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            rate_limit=rl,
            sleep=lambda s: None,
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_rate_limit_async(self):
        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        rl = RateLimiter(max_calls=1, period=0.5)
        rl.acquire()

        result = await backon.retry(
            target,
            backon.constant,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            rate_limit=rl,
        )
        assert result == "ok"


class TestTryAgainStopIteration:
    def test_try_again_stop_iteration_sync(self):
        calls = []

        def target():
            calls.append(1)
            raise TryAgain

        result = _retry_sync_inner(
            target,
            finite_wait,
            condition=backon.retry_always(),
            max_tries=None,
            jitter=None,
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert result is None
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_try_again_stop_iteration_async(self):
        calls = []

        async def target():
            calls.append(1)
            raise TryAgain

        result = await _retry_async_inner(
            target,
            finite_wait,
            condition=backon.retry_always(),
            max_tries=None,
            jitter=None,
            raise_on_giveup=False,
        )
        assert result is None
        assert len(calls) == 2

    def test_try_again_stop_condition_sync(self):
        calls = []

        def target():
            calls.append(1)
            if len(calls) < 3:
                raise TryAgain
            return "ok"

        result = _retry_sync_inner(
            target,
            constant,
            condition=backon.retry_always(),
            max_tries=2,
            jitter=None,
            wait_gen_kwargs={"interval": 0.01},
            sleep=lambda s: None,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_try_again_stop_condition_async(self):
        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 3:
                raise TryAgain
            return "ok"

        result = await _retry_async_inner(
            target,
            constant,
            condition=backon.retry_always(),
            max_tries=2,
            jitter=None,
            wait_gen_kwargs={"interval": 0.01},
        )
        assert result is None


class TestWaitGenEdgeCases:
    def test_combined_wait_add_combined_wait(self):
        w1 = _Wait()
        w2 = _Wait()
        cw = _CombinedWait(w1, w2)
        cw2 = _CombinedWait(w1)
        result = cw + cw2
        assert isinstance(result, _CombinedWait)
        assert len(result._waits) == 3

    def test_wait_random_exponential_min_value(self):
        gen = _WaitRandomExponential(
            multiplier=1, max_value=10, exp_base=2, min_value=5
        )
        val = gen.next(None)
        assert 0 <= val <= 5

    def test_wait_chain_multiple_yields(self):
        from backon._wait_gen import _Constant

        c1 = _Constant(interval=1)
        c2 = _Constant(interval=10)
        gen = _WaitChain(c1, c2)
        assert gen.next(None) == 1
        assert gen.next(None) == 10
        assert gen.next(None) == 1


class TestRetryAttemptSetValue:
    def test_set_value(self):
        attempt = _RetryAttempt()
        attempt.set_value(42)
        assert attempt.value == 42


class TestRetryingStatisticsEdgeCases:
    def test_statistics_with_state_only(self):
        r = Retrying(constant)
        state = RetryState(target=lambda: None)
        state.tries = 3
        state.start_time = 100.0
        r._state = state
        r._call_state = None
        stats = r.statistics
        assert stats["attempt_number"] == 3
        assert stats["start_time"] == 100.0


class TestRetryingIteratorEdgeCases:
    def test_iterator_condition_fail_raise_on_giveup_false(self):
        r = Retrying(constant, exception=ValueError, max_tries=2, jitter=None)
        r._raise_on_giveup = False
        attempts = []
        for attempt in r:
            with attempt:
                raise ValueError("fail")
            attempts.append(attempt)
        assert len(attempts) == 2

    def test_iterator_with_jitter(self):
        r = Retrying(
            constant,
            exception=ValueError,
            max_tries=2,
            jitter=backon.random_jitter,
        )
        r._raise_on_giveup = False
        r._sleep = lambda s: None
        attempts = []
        for attempt in r:
            with attempt:
                raise ValueError("fail")
            attempts.append(attempt)
        assert len(attempts) == 2

    def test_iterator_with_max_time(self):
        r = Retrying(
            constant,
            exception=ValueError,
            max_tries=5,
            max_time=100.0,
            jitter=None,
        )
        r._raise_on_giveup = False
        r._sleep = lambda s: None
        attempts = []
        for attempt in r:
            with attempt:
                raise ValueError("fail")
            attempts.append(attempt)
        assert len(attempts) == 5

    def test_iterator_wait_gen_stop_iteration(self):
        r = Retrying(finite_wait, exception=ValueError, jitter=None)
        r._raise_on_giveup = False
        r._sleep = lambda s: None
        r._max_tries = None
        r._stop = backon.stop_never()
        r._condition = backon.retry_if_exception_type(ValueError)
        attempts = []
        for attempt in r:
            with attempt:
                raise ValueError("fail")
            attempts.append(attempt)
        assert len(attempts) == 2


class TestRetryingCallerAsyncFunction:
    def test_retrying_caller_with_async_raises_typeerror(self):
        async def async_fn(x):
            return x

        caller = RetryingCaller(constant, exception=ValueError, jitter=None)
        with pytest.raises(TypeError, match="Use AsyncRetryingCaller"):
            caller(async_fn, 42)
