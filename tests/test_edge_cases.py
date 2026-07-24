import contextlib
import threading
import time

import pytest

import backon
from backon._common import _maybe_call
from backon._conditions import (
    RetryCondition,
    Stop,
    retry_always,
    retry_if_exception_cause_type,
    retry_if_exception_message,
    retry_if_not_exception_message,
    retry_if_not_exception_type,
    retry_if_not_result,
    retry_never,
    retry_unless_exception_type,
    stop_before_delay,
    stop_never,
    stop_when_event_set,
)
from backon._state import Attempt, RetryCallState, RetryError, RetryState
from backon._wait_gen import (
    _CombinedWait,
    decay,
    expo,
    wait_exponential_jitter,
    wait_incrementing,
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

    def test_stop_before_delay_actually_stops_retry_loop(self):
        attempts = []
        waits = []

        def f():
            attempts.append(1)
            raise ValueError()

        real_sleep = time.sleep

        def fake_sleep(seconds):
            waits.append(seconds)
            real_sleep(seconds)

        with contextlib.suppress(ValueError):
            backon.retry(
                f,
                wait_incrementing,
                exception=ValueError,
                max_tries=20,
                start=0.05,
                increment=0.05,
                jitter=None,
                logger=None,
                sleep=fake_sleep,
                stop=backon.stop_before_delay(0.3),
            )
        assert len(attempts) >= 3
        assert len(attempts) <= 4
        assert sum(waits) < 0.31

    def test_stop_before_delay_predicate_based_actually_stops(self):
        attempts = []
        waits = []

        def f():
            attempts.append(1)
            return

        real_sleep = time.sleep

        def fake_sleep(seconds):
            waits.append(seconds)
            real_sleep(seconds)

        backon.retry(
            f,
            wait_incrementing,
            predicate=lambda r: True,
            max_tries=20,
            start=0.05,
            increment=0.05,
            jitter=None,
            logger=None,
            sleep=fake_sleep,
            stop=backon.stop_before_delay(0.3),
        )
        assert len(attempts) >= 3
        assert len(attempts) <= 4
        assert sum(waits) < 0.31

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
        val = gen.next()
        assert val > 0
        for _ in range(100):
            val = gen.next()
        assert val == 1

    def test_wait_random_exponential_with_limits(self):
        gen = wait_random_exponential(
            multiplier=1, max_value=10, exp_base=2, min_value=0.5
        )
        for _ in range(20):
            val = gen.next()
            assert val <= 10

    def test_wait_random_exponential_without_limits(self):
        gen = wait_random_exponential()
        for _ in range(10):
            val = gen.next()
            assert val >= 0

    def test_wait_incrementing_with_max(self):
        gen = wait_incrementing(start=5, increment=5, max_value=12)
        for _ in range(10):
            val = gen.next()
            assert val <= 12

    def test_wait_incrementing_without_max(self):
        gen = wait_incrementing(start=1, increment=2)
        val = gen.next()
        assert val == 1
        val = gen.next()
        assert val == 3

    def test_wait_exception(self):
        from backon._wait_gen import _WaitException

        gen = _WaitException(value=lambda e: 2.0)
        val = gen.next(ValueError())
        assert val == 2.0

    def test_wait_chain(self):
        from backon._wait_gen import _Constant, _WaitChain

        c1 = _Constant(interval=1)
        c2 = _Constant(interval=0.5)
        gen = _WaitChain(c1, c2)
        val = gen.next(None)
        assert val == 1
        val = gen.next(None)
        assert val == 0.5

    def test_wait_chain_stop_iteration(self):
        from backon._wait_gen import _Constant, _WaitChain

        c1 = _Constant(interval=1)
        c2 = _Constant(interval=0.0)
        gen = _WaitChain(c1, c2)
        val = gen.next(None)
        assert val == 1
        val = gen.next(None)
        assert val == 0.0

    def test_wait_radd(self):
        from backon._wait_gen import _Constant

        w = _Constant()
        result = 1 + w
        assert isinstance(result, _CombinedWait)

    def test_combined_wait_add_combined(self):
        from backon._wait_gen import _Constant

        w1 = _Constant()
        w2 = _Constant()
        cw = _CombinedWait(w1, w2)
        w3 = _Constant()
        result = cw + w3
        assert isinstance(result, _CombinedWait)
        assert len(result._waits) == 3

    def test_wait_random_basic(self):
        gen = wait_random(min=1, max=2)
        val = gen.next()
        assert 1 <= val <= 2

    def test_wait_exponential_jitter(self):
        gen = wait_exponential_jitter(initial=1, max=60, exp_base=2, jitter=1)
        for _ in range(5):
            val = gen.next()
            assert val >= 0

    def test_expo_max_value(self):
        gen = expo(base=2, factor=1, max_value=3)
        for _ in range(10):
            val = gen.next()
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
            return

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
            return

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
        val = gen.next()
        assert val == 2.0

    def test_combined_wait_with_jitter(self):
        combined = expo + backon.constant
        gen = combined()
        val = gen.next()
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


class TestBaseExceptionPropagation:
    def test_keyboard_interrupt_propagates_raise_on_giveup_false(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        def fn():
            raise KeyboardInterrupt("abort")

        with pytest.raises(KeyboardInterrupt):
            fn()

    def test_system_exit_propagates_raise_on_giveup_false(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        def fn():
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            fn()

    def test_generator_exit_propagates_raise_on_giveup_false(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        def fn():
            raise GeneratorExit()

        with pytest.raises(GeneratorExit):
            fn()

    def test_keyboard_interrupt_propagates_through_retry_func(self):
        def fn():
            raise KeyboardInterrupt("abort")

        with pytest.raises(KeyboardInterrupt):
            backon.retry(
                fn,
                backon.constant,
                exception=ValueError,
                max_tries=3,
                jitter=None,
                interval=0.01,
                raise_on_giveup=False,
                sleep=lambda s: None,
                logger=None,
            )

    def test_keyboard_interrupt_propagates_through_retrying(self):
        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        with pytest.raises(KeyboardInterrupt):
            r.call(lambda: (_ for _ in ()).throw(KeyboardInterrupt("abort")))

    @pytest.mark.asyncio
    async def test_async_keyboard_interrupt_propagates(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        async def fn():
            raise KeyboardInterrupt("abort")

        with pytest.raises(KeyboardInterrupt):
            await fn()

    @pytest.mark.asyncio
    async def test_async_system_exit_propagates(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        async def fn():
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            await fn()

    def test_raise_on_giveup_true_still_propagates_keyboard_interrupt(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            raise_on_giveup=True,
            sleep=lambda s: None,
            logger=None,
        )
        def fn():
            raise KeyboardInterrupt("abort")

        with pytest.raises(KeyboardInterrupt):
            fn()


class TestCommonGaps:
    def test_maybe_call_typeerror_propagates(self):
        class _TypeErrorRaiser:
            def __call__(self, x):
                raise TypeError("internal error in function")

        with pytest.raises(TypeError, match="internal error"):
            _maybe_call(_TypeErrorRaiser(), 42)

    def test_config_handlers_with_logger_and_iterable_on_backoff(self):
        calls = []

        def f():
            calls.append(1)
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            backon.retry(
                f,
                backon.constant,
                exception=ValueError,
                max_tries=3,
                jitter=None,
                interval=0.01,
                logger="test",
                on_backoff=[lambda d: None, lambda d: None],
                sleep=lambda s: None,
            )
        assert len(calls) == 3

    def test_config_handlers_logger_no_user_handlers(self):
        import logging

        from backon._common import _config_handlers, _log_backoff

        handlers = _config_handlers(
            None,
            default_handler=_log_backoff,
            logger=logging.getLogger("test_gap"),
            log_level=logging.INFO,
        )
        assert len(handlers) == 1


class TestStateGaps:
    def test_retry_error_no_cause_at_all(self):
        attempt = Attempt(exception=None, tries=1)
        err = RetryError(attempt)
        assert err.last_attempt is attempt
        assert err.__cause__ is None

    def test_retry_error_reraise_no_exception(self):
        attempt = Attempt(exception=None, tries=1)
        err = RetryError(attempt)
        err.reraise()


class TestConditionsGaps:
    def test_retry_if_not_exception_type_sequence(self):
        c = retry_if_not_exception_type((ValueError, TypeError))
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("x"))
        assert c(state) is False

    def test_paramspec_stub_exists(self):

        from backon._typing import ParamSpec

        ps = ParamSpec("P")
        assert ps is not None


class TestWaitGenGaps:
    def test_wait_base_next_raises(self):
        from backon._wait_gen import _Wait

        w = _Wait()
        with pytest.raises(NotImplementedError):
            w.next()

    def test_constant_empty_iterable(self):
        from backon._wait_gen import constant

        g = constant(interval=[])
        with pytest.raises(StopIteration):
            g.next()

    def test_wait_add_with_combined_wait(self):
        from backon._wait_gen import _CombinedWait, _Constant, _Wait

        w = _Wait()
        cw = _CombinedWait(_Constant(), _Constant())
        result = w + cw
        assert isinstance(result, _CombinedWait)
        assert len(result._waits) == 3

    def test_wait_add_non_combined(self):
        from backon._wait_gen import _CombinedWait, _Wait

        w = _Wait()
        result = w + 1
        assert isinstance(result, _CombinedWait)

    def test_wait_factory_radd_with_combined_wait(self):
        from backon._wait_gen import _CombinedWait, _Wait, expo

        w = _Wait()
        cw = _CombinedWait(w, w)
        result = expo.__radd__(cw)
        assert isinstance(result, _CombinedWait)
        assert len(result._waits) == 3

    def test_wait_factory_radd_with_non_wait(self):
        from backon._wait_gen import _CombinedWait, expo

        class _NonAddable:
            pass

        result = _NonAddable() + expo
        assert isinstance(result, _CombinedWait)

    def test_wait_call_with_many_args(self):
        from backon._wait_gen import _Wait

        w = _Wait(kw1=1, kw2=2)
        g = w(2, 3, 4)
        assert isinstance(g, _Wait)

    def test_wait_chain_empty(self):
        from backon._wait_gen import _WaitChain

        wc = _WaitChain()
        assert wc.next() == 0.0

    def test_combined_wait_add_combined_wait(self):
        from backon._wait_gen import _CombinedWait, _Constant, expo

        cw1 = _CombinedWait(_Constant(), _Constant())
        cw2 = _CombinedWait(_Constant(), _Constant())
        result = cw1 + cw2
        assert isinstance(result, _CombinedWait)
        assert len(result._waits) == 4

        result2 = expo + cw1
        assert isinstance(result2, _CombinedWait)


class TestHelpersGaps:
    def test_make_default_condition_giveup_returns_string(self):
        from backon._retry._helpers import _make_default_condition

        condition = _make_default_condition(
            exception=ValueError,
            giveup=lambda e: "retry",
            predicate=lambda x: False,
        )
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        assert condition(state) is True


class TestCommonMoreGaps:
    def test_config_handlers_logger_with_single_handler(self):
        import logging

        from backon._common import _config_handlers, _log_backoff

        handlers = _config_handlers(
            lambda d: None,
            default_handler=_log_backoff,
            logger="test",
            log_level=logging.INFO,
        )
        assert len(handlers) == 2


class TestDecoratorGenDisabled:
    @pytest.mark.asyncio
    async def test_on_exception_async_gen_disabled(self):
        backon.disable()
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            sleep=lambda s: None,
            logger=None,
        )
        async def gen():
            calls.append(1)
            yield 42

        result = []
        async for item in gen():
            result.append(item)
        assert result == [42]
        assert len(calls) == 1
        backon.enable()

    def test_on_exception_sync_gen_disabled(self):
        backon.disable()
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            sleep=lambda s: None,
            logger=None,
        )
        def gen():
            calls.append(1)
            yield 42

        result = list(gen())
        assert result == [42]
        assert len(calls) == 1
        backon.enable()


class TestRetryingIteratorEdgeCases:
    def test_retrying_iterator_condition_fails_giveup_false(self):
        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            raise_on_giveup=False,
            sleep=lambda s: None,
            logger=None,
        )
        r._condition = backon.retry_never()
        for attempt in r:
            with attempt:
                raise ValueError("fail")

    def test_retrying_iterator_seconds_gt_zero(self):
        waits = []

        def track(s):
            waits.append(s)

        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            sleep=track,
            logger=None,
            raise_on_giveup=False,
        )
        for attempt in r:
            with attempt:
                raise ValueError("fail")
        assert len(waits) >= 1


class TestInnerEdgeCases:
    def test_sync_inner_stop_none(self):
        from backon._retry._inner import _retry_sync_inner

        calls = []

        def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            _retry_sync_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=2,
                jitter=None,
                sleep=lambda s: None,
                stop=None,
                wait_gen_kwargs={"interval": 0.01},
            )
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_async_inner_stop_none(self):
        from backon._retry._inner import _retry_async_inner

        calls = []

        async def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await _retry_async_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=2,
                jitter=None,
                stop=None,
                wait_gen_kwargs={"interval": 0.01},
            )
        assert len(calls) == 2


class TestDecideStopReturnsTrue:
    def test_attempt_timeout_with_stop_true(self):
        from backon._retry._decide import _decide_outcome, _RetryAction

        state = RetryState(target=lambda: 42)
        state.tries = 5
        state.elapsed = 0.5
        state.outcome = Attempt(exception=backon.AttemptTimeoutError(), tries=5)
        call_state = RetryCallState()
        stop = backon.stop_after_attempt(3)
        action, _seconds, _details, _use_cb, suppress = _decide_outcome(
            state,
            call_state,
            None,
            lambda s: True,
            stop,
            jitter=None,
            max_time=None,
            exc=backon.AttemptTimeoutError(),
            ret=None,
        )
        assert action == _RetryAction.GIVEUP
        assert suppress is True

    def test_exc_custom_wait_with_stop_true(self):
        from backon._retry._decide import _decide_outcome, _RetryAction

        state = RetryState(target=lambda: 42)
        state.tries = 5
        state.elapsed = 0.5
        state.outcome = Attempt(exception=ValueError("fail"), tries=5)
        call_state = RetryCallState()
        stop = backon.stop_after_attempt(3)
        action, *_ = _decide_outcome(
            state,
            call_state,
            None,
            lambda s: 0.05,
            stop,
            jitter=None,
            max_time=None,
            exc=ValueError("fail"),
            ret=None,
        )
        assert action == _RetryAction.GIVEUP

    def test_exc_condition_true_with_stop_true(self):
        from backon._retry._decide import _decide_outcome, _RetryAction
        from backon._wait_gen import constant

        state = RetryState(target=lambda: 42)
        state.tries = 5
        state.elapsed = 0.5
        state.outcome = Attempt(exception=ValueError("fail"), tries=5)
        call_state = RetryCallState()
        wait = constant(interval=0.01)
        stop = backon.stop_after_attempt(3)
        action, *_ = _decide_outcome(
            state,
            call_state,
            wait,
            lambda s: True,
            stop,
            jitter=None,
            max_time=None,
            exc=ValueError("fail"),
            ret=None,
        )
        assert action == _RetryAction.GIVEUP

    def test_ret_custom_wait_with_stop_true(self):
        from backon._retry._decide import _decide_outcome, _RetryAction

        state = RetryState(target=lambda: 42)
        state.tries = 5
        state.elapsed = 0.5
        state.outcome = Attempt(value=42, tries=5)
        call_state = RetryCallState()
        stop = backon.stop_after_attempt(3)
        action, *_ = _decide_outcome(
            state,
            call_state,
            None,
            lambda s: 0.05,
            stop,
            jitter=None,
            max_time=None,
            exc=None,
            ret=42,
        )
        assert action == _RetryAction.GIVEUP

    def test_ret_condition_true_with_stop_true(self):
        from backon._retry._decide import _decide_outcome, _RetryAction
        from backon._wait_gen import constant

        state = RetryState(target=lambda: 42)
        state.tries = 5
        state.elapsed = 0.5
        state.outcome = Attempt(value=42, tries=5)
        call_state = RetryCallState()
        wait = constant(interval=0.01)
        stop = backon.stop_after_attempt(3)
        action, *_ = _decide_outcome(
            state,
            call_state,
            wait,
            lambda s: True,
            stop,
            jitter=None,
            max_time=None,
            exc=None,
            ret=42,
        )
        assert action == _RetryAction.GIVEUP

    def test_attempt_timeout_stop_before_delay_second_check(self):
        from backon._retry._decide import _decide_outcome, _RetryAction
        from backon._wait_gen import constant

        state = RetryState(target=lambda: 42)
        state.tries = 1
        state.elapsed = 0.4
        state.outcome = Attempt(exception=backon.AttemptTimeoutError(), tries=1)
        call_state = RetryCallState()
        wait = constant(interval=0.2)
        stop = backon.stop_before_delay(0.5)
        action, *_ = _decide_outcome(
            state,
            call_state,
            wait,
            lambda s: True,
            stop,
            jitter=None,
            max_time=None,
            exc=backon.AttemptTimeoutError(),
            ret=None,
        )
        assert action == _RetryAction.GIVEUP


class TestRetryingIteratorZeroWait:
    def test_seconds_eq_zero_skips_sleep(self):
        from backon._wait_gen import wait_none

        waits = []

        def track(s):
            waits.append(s)

        r = backon.Retrying(
            wait_none,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            raise_on_giveup=False,
            sleep=track,
            logger=None,
        )
        for attempt in r:
            with attempt:
                raise ValueError("fail")
        assert len(waits) == 0


class TestInnerStopNotNone:
    def test_sync_inner_stop_not_none(self):
        from backon._retry._inner import _retry_sync_inner

        calls = []

        def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            _retry_sync_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=5,
                jitter=None,
                sleep=lambda s: None,
                stop=backon.stop_after_attempt(2),
                wait_gen_kwargs={"interval": 0.01},
            )
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_async_inner_stop_not_none(self):
        from backon._retry._inner import _retry_async_inner

        calls = []

        async def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await _retry_async_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=5,
                jitter=None,
                stop=backon.stop_after_attempt(2),
                wait_gen_kwargs={"interval": 0.01},
            )
        assert len(calls) == 2


class TestAsyncLoopTryAgain:
    @pytest.mark.asyncio
    async def test_async_loop_try_again_positive_wait(self):
        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 2:
                raise backon.TryAgain
            return "ok"

        result = await backon.retry(
            target,
            backon.constant,
            condition=backon.retry_always(),
            max_tries=3,
            jitter=None,
            interval=0.01,
            logger=None,
            on_backoff=lambda d: None,
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_async_loop_try_again_zero_wait(self):
        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 2:
                raise backon.TryAgain
            return "ok"

        result = await backon.retry(
            target,
            backon.wait_none,
            condition=backon.retry_always(),
            max_tries=3,
            jitter=None,
            logger=None,
            on_backoff=lambda d: None,
        )
        assert result == "ok"
