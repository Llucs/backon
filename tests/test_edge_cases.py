import threading
import time

import pytest

import backon
from backon._common import _maybe_call
from backon._conditions import (
    RetryCondition,
    Stop,
    retry_if_exception_cause_type,
    retry_if_exception_message,
    retry_if_not_exception_message,
    retry_if_not_exception_type,
    retry_if_not_result,
    retry_unless_exception_type,
    retry_always,
    retry_never,
    stop_before_delay,
    stop_never,
    stop_when_event_set,
)
from backon._state import Attempt, RetryCallState, RetryError, RetryState
from backon._wait_gen import (
    _CombinedWait,
    _Wait,
    decay,
    expo,
    wait_chain,
    wait_exception,
    wait_exponential_jitter,
    wait_incrementing,
    wait_none,
    wait_random,
    wait_random_exponential,
)


class TestCommonEdgeCases:
    def test_maybe_call_typeerror_fallback(self):
        def f():
            pass

        result = _maybe_call(f, "unexpected_arg")
        assert result is f

    def test_maybe_call_noncallable(self):
        assert _maybe_call(42) == 42

    def test_maybe_call_callable_success(self):
        assert _maybe_call(lambda x: x + 1, 41) == 42


class TestStateEdgeCases:
    def test_retry_error_with_cause(self):
        cause = ValueError("root cause")
        try:
            raise TypeError("wrapper") from cause
        except TypeError as exc:
            attempt = Attempt(exception=exc, tries=3)
            err = RetryError(attempt)
            assert err.last_attempt is attempt
            assert err.__cause__ is exc
            assert err.__cause__.__cause__ is cause

    def test_retry_error_reraise(self):
        try:
            raise TypeError("wrapper") from ValueError("root cause")
        except TypeError as exc:
            attempt = Attempt(exception=exc, tries=3)
            err = RetryError(attempt)
            with pytest.raises(TypeError):
                err.reraise()

    def test_retry_error_reraise_no_cause(self):
        attempt = Attempt(exception=ValueError("no cause"), tries=1)
        err = RetryError(attempt)
        with pytest.raises(ValueError):
            err.reraise()

    def test_retry_error_no_cause(self):
        attempt = Attempt(exception=ValueError("solo"), tries=1)
        err = RetryError(attempt)
        assert err.__cause__ is attempt.exception
        assert str(err) == "Retry failed after 1 tries"

    def test_retry_state_statistics_has_start_time(self):
        state = RetryState(target=lambda: None)
        state.start_time = 12345.0
        state.tries = 5
        stats = state.statistics
        assert stats["start_time"] == 12345.0
        assert stats["attempt_number"] == 5

    def test_retry_call_state_seconds_since_start(self):
        state = RetryCallState(start_time=time.monotonic())
        time.sleep(0.01)
        assert state.seconds_since_start > 0


class TestConditionsEdgeCases:
    def test_stop_base_raises(self):
        s = Stop()
        with pytest.raises(NotImplementedError):
            s(RetryState())

    def test_retry_condition_base_raises(self):
        c = RetryCondition()
        with pytest.raises(NotImplementedError):
            c(RetryState())

    def test_stop_never(self):
        s = stop_never()
        assert s(RetryState()) is False

    def test_stop_before_delay_with_outcome_wait(self):
        state = RetryState()
        state.outcome = Attempt(wait=0.5)
        state.elapsed = 2.0
        s = stop_before_delay(2.3)
        assert s(state) is True

    def test_stop_before_delay_no_outcome(self):
        state = RetryState()
        state.elapsed = 0.5
        s = stop_before_delay(1.0)
        assert s(state) is False

    def test_stop_when_event_set(self):
        event = threading.Event()
        s = stop_when_event_set(event)
        state = RetryState()
        assert s(state) is False
        event.set()
        assert s(state) is True

    def test_retry_always(self):
        c = retry_always()
        state = RetryState()
        state.outcome = Attempt(exception=ValueError())
        assert c(state) is True

    def test_retry_never(self):
        c = retry_never()
        state = RetryState()
        state.outcome = Attempt(exception=ValueError())
        assert c(state) is False

    def test_retry_if_exception_with_predicate(self):
        c = backon.retry_if_exception(lambda e: "fatal" in str(e))
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fatal error"))
        assert c(state) is True
        state.outcome = Attempt(exception=ValueError("minor"))
        assert c(state) is False

    def test_retry_if_exception_outcome_none(self):
        c = backon.retry_if_exception(lambda e: True)
        state = RetryState()
        assert c(state) is False

    def test_retry_if_exception_message_regex(self):
        c = retry_if_exception_message("foo.*bar", match="re")
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("foo and bar"))
        assert c(state) is True

    def test_retry_if_exception_message_substring(self):
        c = retry_if_exception_message("timeout")
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("request timeout"))
        assert c(state) is True
        state.outcome = Attempt(exception=ValueError("other"))
        assert c(state) is False

    def test_retry_if_exception_message_outcome_none(self):
        c = retry_if_exception_message("x")
        state = RetryState()
        assert c(state) is False

    def test_retry_if_exception_message_exc_none(self):
        c = retry_if_exception_message("x")
        state = RetryState()
        state.outcome = Attempt()
        assert c(state) is False

    def test_retry_if_result_outcome_none(self):
        c = backon.retry_if_result(lambda x: x is None)
        state = RetryState()
        assert c(state) is False

    def test_retry_if_result_outcome_exception(self):
        c = backon.retry_if_result(lambda x: True)
        state = RetryState()
        state.outcome = Attempt(exception=ValueError())
        assert c(state) is False

    def test_retry_if_not_result_outcome_none(self):
        c = retry_if_not_result(lambda x: x is None)
        state = RetryState()
        assert c(state) is False

    def test_retry_if_not_result_outcome_exception(self):
        c = retry_if_not_result(lambda x: True)
        state = RetryState()
        state.outcome = Attempt(exception=ValueError())
        assert c(state) is False

    def test_retry_if_not_result_matches(self):
        c = retry_if_not_result(lambda x: x == 42)
        state = RetryState()
        state.outcome = Attempt(value=0)
        assert c(state) is True

    def test_retry_if_not_exception_type_outcome_none(self):
        c = retry_if_not_exception_type(ValueError)
        state = RetryState()
        assert c(state) is False

    def test_retry_if_not_exception_type_mismatch(self):
        c = retry_if_not_exception_type(ValueError)
        state = RetryState()
        state.outcome = Attempt(exception=TypeError())
        assert c(state) is True

    def test_retry_if_not_exception_type_match(self):
        c = retry_if_not_exception_type(ValueError)
        state = RetryState()
        state.outcome = Attempt(exception=ValueError())
        assert c(state) is False

    def test_retry_unless_exception_type_outcome_none(self):
        c = retry_unless_exception_type(ValueError)
        state = RetryState()
        assert c(state) is False

    def test_retry_if_not_exception_message_regex(self):
        c = retry_if_not_exception_message("foo", regex=True)
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("bar"))
        assert c(state) is True
        state.outcome = Attempt(exception=ValueError("foo"))
        assert c(state) is False

    def test_retry_if_exception_cause_type_direct(self):
        c = retry_if_exception_cause_type(ValueError)
        state = RetryState()
        state.outcome = Attempt(exception=TypeError("wraps"))
        assert c(state) is False

    def test_retry_if_exception_cause_type_with_cause(self):
        c = retry_if_exception_cause_type(ValueError)
        state = RetryState()
        cause = ValueError("root")
        exc = TypeError("wrapper")
        exc.__cause__ = cause
        state.outcome = Attempt(exception=exc)
        assert c(state) is True

    def test_retry_if_exception_cause_type_outcome_none(self):
        c = retry_if_exception_cause_type(ValueError)
        state = RetryState()
        assert c(state) is False

    def test_retry_if_exception_cause_type_exc_none(self):
        c = retry_if_exception_cause_type(ValueError)
        state = RetryState()
        state.outcome = Attempt()
        assert c(state) is False

    def test_retry_all_and_any(self):
        state = RetryState()
        state.outcome = Attempt(exception=ValueError())
        c1 = retry_always()
        c2 = retry_never()
        assert backon.retry_all(c1, c1)(state) is True
        assert backon.retry_all(c1, c2)(state) is False
        assert backon.retry_any(c1, c2)(state) is True
        assert backon.retry_any(c2, c2)(state) is False

    def test_stop_operators(self):
        s1 = backon.stop_after_attempt(3)
        s2 = backon.stop_after_attempt(5)
        combined_or = s1 | s2
        combined_and = s1 & s2
        assert isinstance(combined_or, backon.stop_any)
        assert isinstance(combined_and, backon.stop_all)

    def test_retry_condition_operators(self):
        c1 = backon.retry_if_exception_type(ValueError)
        c2 = backon.retry_if_exception_type(TypeError)
        combined_or = c1 | c2
        combined_and = c1 & c2
        assert isinstance(combined_or, backon.retry_any)
        assert isinstance(combined_and, backon.retry_all)


class TestWaitGenEdgeCases:
    def test_decay_with_min_value(self):
        gen = decay(initial_value=10, decay_factor=2, min_value=1)
        next(gen)
        val = gen.send(None)
        assert val > 0
        for _ in range(100):
            val = gen.send(None)
        assert val == 1

    def test_wait_random_exponential_with_limits(self):
        gen = wait_random_exponential(
            multiplier=1, max_value=10, exp_base=2, min_value=0.5
        )
        next(gen)
        for _ in range(20):
            val = gen.send(None)
            assert val <= 10

    def test_wait_random_exponential_without_limits(self):
        gen = wait_random_exponential()
        next(gen)
        for _ in range(10):
            val = gen.send(None)
            assert val >= 0

    def test_wait_incrementing_with_max(self):
        gen = wait_incrementing(start=5, increment=5, max_value=12)
        next(gen)
        for _ in range(10):
            val = gen.send(None)
            assert val <= 12

    def test_wait_incrementing_without_max(self):
        gen = wait_incrementing(start=1, increment=2)
        next(gen)
        val = gen.send(None)
        assert val == 1
        val = gen.send(None)
        assert val == 3

    def test_wait_exception(self):
        from backon._wait_gen import _wait_exception

        gen = _wait_exception(value=lambda e: 2.0)
        next(gen)
        val = gen.send(ValueError())
        assert val == 2.0

    def test_wait_chain(self):
        from backon._wait_gen import _wait_chain, _constant

        def g1():
            yield 0
            yield 1

        g2 = _constant(interval=0.5)
        gen = _wait_chain(g1(), g2)
        next(gen)
        val = gen.send(None)
        assert val == 1
        val = gen.send(None)
        assert val == 0.5

    def test_wait_chain_stop_iteration(self):
        from backon._wait_gen import _wait_chain

        def finite_gen():
            yield 0
            yield 1

        g1 = finite_gen()
        g2 = wait_none()
        gen = _wait_chain(g1, g2)
        next(gen)
        val = gen.send(None)
        assert val == 1
        val = gen.send(None)
        assert val == 0.0

    def test_wait_radd(self):
        w = _Wait(lambda: iter([0.0]))
        result = 1 + w
        assert isinstance(result, _CombinedWait)

    def test_combined_wait_add_combined(self):
        w1 = _Wait(lambda: iter([0.0]))
        w2 = _Wait(lambda: iter([0.0]))
        cw = _CombinedWait(w1, w2)
        w3 = _Wait(lambda: iter([0.0]))
        result = cw + w3
        assert isinstance(result, _CombinedWait)
        assert len(result._waits) == 3

    def test_wait_random_basic(self):
        gen = wait_random(min=1, max=2)
        next(gen)
        val = gen.send(None)
        assert 1 <= val <= 2

    def test_wait_exponential_jitter(self):
        gen = wait_exponential_jitter(initial=1, max=60, exp_base=2, jitter=1)
        next(gen)
        for _ in range(5):
            val = gen.send(None)
            assert val >= 0

    def test_expo_max_value(self):
        gen = expo(base=2, factor=1, max_value=3)
        next(gen)
        for _ in range(10):
            val = gen.send(None)
            assert val <= 3


class TestTryAgain:
    def test_try_again_sync(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
        )
        def f():
            calls.append(1)
            if len(calls) == 1:
                raise backon.TryAgain
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        assert f() == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_try_again_async(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
        )
        async def f():
            calls.append(1)
            if len(calls) == 1:
                raise backon.TryAgain
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        assert await f() == "ok"
        assert len(calls) == 3

    def test_try_again_giveup_after_max_tries(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
        )
        def f():
            calls.append(1)
            raise backon.TryAgain

        result = f()
        assert result is None
        assert len(calls) == 2


class TestRetryErrorCallback:
    def test_retry_error_callback_sync(self):
        def error_cb(details):
            return "fallback"

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            retry_error_callback=error_cb,
        )
        def f():
            raise ValueError("fail")

        assert f() == "fallback"

    @pytest.mark.asyncio
    async def test_retry_error_callback_async(self):
        def error_cb(details):
            return "fallback"

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            retry_error_callback=error_cb,
        )
        async def f():
            raise ValueError("fail")

        assert await f() == "fallback"


class TestRetryingEdgeCases:
    def test_retrying_enabled_setter(self):
        r = backon.Retrying(backon.constant)
        assert r.enabled is True
        r.enabled = False
        assert r.enabled is False

    def test_retrying_call_async_raises_typeerror(self):
        async def async_fn():
            pass

        r = backon.Retrying(backon.constant)
        with pytest.raises(TypeError, match="Use await"):
            r.call(async_fn)

    def test_retrying_iterator_raise_on_giveup_false(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        r = backon.Retrying(
            backon.expo,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            raise_on_giveup=False,
        )
        for attempt in r:
            with attempt:
                flaky()
            if not attempt.failed:
                break

        assert len(calls) == 2

    def test_retrying_iterator_stop_after_success(self):
        calls = []

        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        for attempt in r:
            with attempt:
                calls.append(1)
            if not attempt.failed:
                break

        assert len(calls) == 1


class TestDecoratorEdgeCases:
    def test_on_exception_with_giveup(self):
        calls = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=5,
            jitter=None,
            giveup=lambda e: "fatal" in str(e),
        )
        def f():
            calls.append(1)
            raise ValueError("fatal error")

        with pytest.raises(ValueError):
            f()
        assert len(calls) == 1

    def test_on_exception_multiple_exception_types(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            (ValueError, TypeError),
            max_tries=2,
            jitter=None,
            interval=0.01,
        )
        def f():
            calls.append(1)
            if len(calls) == 1:
                raise TypeError("type error")
            raise ValueError("value error")

        with pytest.raises(ValueError):
            f()
        assert len(calls) == 2

    def test_on_predicate_disabled(self):
        backon.disable()
        calls = []

        @backon.on_predicate(backon.expo, max_tries=5, jitter=None)
        def f():
            calls.append(1)
            return None

        f()
        assert len(calls) == 1
        backon.enable()

    @pytest.mark.asyncio
    async def test_on_predicate_disabled_async(self):
        backon.disable()
        calls = []

        @backon.on_predicate(backon.expo, max_tries=5, jitter=None)
        async def f():
            calls.append(1)
            return None

        await f()
        assert len(calls) == 1
        backon.enable()


class TestSleepUsingEvent:
    def test_sleep_using_event(self):
        event = threading.Event()
        sleep_fn = backon.sleep_using_event(event)
        start = time.time()
        sleep_fn(0.01)
        elapsed = time.time() - start
        assert elapsed >= 0.009


class TestWaitGenComposition:
    def test_expo_plus_constant(self):
        combined = expo + backon.constant
        gen = combined()
        gen.send(None)
        val = gen.send(None)
        assert val == 2.0

    def test_combined_wait_with_jitter(self):
        combined = expo + backon.constant
        gen = combined()
        gen.send(None)
        val = gen.send(None)
        assert val >= 0

    def test_combined_wait_with_jitter(self):
        combined = expo + backon.constant
        gen = combined()
        gen.send(None)
        val = gen.send(None)
        assert val > 0


class TestMakeDefaultConditionWithGiveup:
    def test_giveup_condition_not_matching_exc_type(self):
        from backon._retry import _make_default_condition

        condition = _make_default_condition(
            exception=ValueError,
            giveup=lambda e: "skip" in str(e),
            predicate=lambda x: False,
        )
        state = RetryState()
        state.outcome = Attempt(exception=TypeError("skip"))
        assert condition(state) is False

    def test_giveup_condition_matching_giveup(self):
        from backon._retry import _make_default_condition

        condition = _make_default_condition(
            exception=ValueError,
            giveup=lambda e: "fatal" in str(e),
            predicate=lambda x: False,
        )
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fatal error"))
        assert condition(state) is False

    def test_giveup_condition_not_giving_up(self):
        from backon._retry import _make_default_condition

        condition = _make_default_condition(
            exception=ValueError,
            giveup=lambda e: "fatal" in str(e),
            predicate=lambda x: False,
        )
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("minor"))
        assert condition(state) is True


class TestOnExceptionGiveupCondition:
    def test_on_exception_giveup_condition_not_matching_exc_type(self):
        calls = []

        @backon.on_exception(
            backon.expo,
            (ValueError, TypeError),
            max_tries=3,
            jitter=None,
            giveup=lambda e: "fatal" in str(e),
        )
        def f():
            calls.append(1)
            raise KeyError("not our type")

        with pytest.raises(KeyError):
            f()
        assert len(calls) == 1
