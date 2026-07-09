import random
from datetime import timedelta

import pytest

import backon
from backon._conditions import (
    retry_all,
    retry_any,
    retry_if_exception_cause_type,
    retry_if_exception_type,
    retry_if_not_exception_message,
    retry_if_not_exception_type,
    retry_unless_exception_type,
    stop_after_attempt,
    stop_after_delay,
    stop_all,
    stop_any,
)
from backon._retry import Retrying, _RetryAttempt, _to_seconds
from backon._state import Attempt, AttemptResult, RetryState
from backon._wait_gen import (
    _CombinedWait,
    constant,
    expo,
    fibo,
    wait_exponential_jitter,
    wait_none,
    wait_random,
)


class TestStopOperatorOverloading:
    def test_stop_or_produces_stop_any(self):
        s1 = stop_after_attempt(3)
        s2 = stop_after_delay(10)
        combined = s1 | s2
        assert isinstance(combined, stop_any)
        assert len(combined.stops) == 2
        assert combined.stops[0] is s1
        assert combined.stops[1] is s2

    def test_stop_and_produces_stop_all(self):
        s1 = stop_after_attempt(3)
        s2 = stop_after_delay(10)
        combined = s1 & s2
        assert isinstance(combined, stop_all)
        assert len(combined.stops) == 2
        assert combined.stops[0] is s1
        assert combined.stops[1] is s2

    def test_stop_any_stops_when_any_true(self):
        state = RetryState(target=lambda: None)
        state.tries = 5
        state.elapsed = 0.001
        stop = stop_after_attempt(3) | stop_after_delay(999)
        assert stop(state) is True

    def test_stop_all_stops_when_all_true(self):
        state = RetryState(target=lambda: None)
        state.tries = 5
        state.elapsed = 999
        stop = stop_after_attempt(3) & stop_after_delay(1)
        assert stop(state) is True

    def test_stop_all_does_not_stop_when_one_false(self):
        state = RetryState(target=lambda: None)
        state.tries = 1
        state.elapsed = 999
        stop = stop_after_attempt(3) & stop_after_delay(1)
        assert stop(state) is False

    def test_stop_any_does_not_stop_when_all_false(self):
        state = RetryState(target=lambda: None)
        state.tries = 1
        state.elapsed = 0.001
        stop = stop_after_attempt(3) | stop_after_delay(999)
        assert stop(state) is False

    def test_combined_stop_stops_after_max_attempts(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        stop_cond = stop_after_attempt(2) | stop_after_delay(999)
        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.constant,
                exception=ValueError,
                stop=stop_cond,
                jitter=None,
                interval=0.01,
            )
        assert len(calls) == 2

    def test_stop_all_requires_both_conditions(self):
        state = RetryState(target=lambda: None)
        state.tries = 5
        state.elapsed = 10
        stop = stop_after_attempt(3) & stop_after_delay(1)
        assert stop(state) is True

        state.tries = 2
        state.elapsed = 10
        assert stop(state) is False

        state.tries = 5
        state.elapsed = 0.001
        assert stop(state) is False


class TestRetryConditionOperatorOverloading:
    def test_condition_or_produces_retry_any(self):
        c1 = retry_if_exception_type(ValueError)
        c2 = retry_if_exception_type(TypeError)
        combined = c1 | c2
        assert isinstance(combined, retry_any)
        assert len(combined.conditions) == 2

    def test_condition_and_produces_retry_all(self):
        c1 = retry_if_exception_type(ValueError)
        c2 = retry_if_exception_type(TypeError)
        combined = c1 & c2
        assert isinstance(combined, retry_all)
        assert len(combined.conditions) == 2

    def test_retry_any_retries_when_either_matches(self):
        c1 = retry_if_exception_type(ValueError)
        c2 = retry_if_exception_type(TypeError)
        combined = c1 | c2

        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=ValueError("test"))
        assert combined(state) is True

        state.outcome = Attempt(exception=TypeError("test"))
        assert combined(state) is True

    def test_retry_any_does_not_retry_when_neither_matches(self):
        c1 = retry_if_exception_type(ValueError)
        c2 = retry_if_exception_type(TypeError)
        combined = c1 | c2

        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=RuntimeError("test"))
        assert combined(state) is False

    def test_retry_all_retries_when_both_match(self):
        class BothError(ValueError, TypeError):
            pass

        c1 = retry_if_exception_type(ValueError)
        c2 = retry_if_exception_type(TypeError)
        combined = c1 & c2

        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=BothError())
        assert combined(state) is True

    def test_retry_all_does_not_retry_when_only_one_matches(self):
        c1 = retry_if_exception_type(ValueError)
        c2 = retry_if_exception_type(TypeError)
        combined = c1 & c2

        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=ValueError("test"))
        assert combined(state) is False

    def test_combined_condition_retries_with_real_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        cond = retry_if_exception_type(ValueError) | retry_if_exception_type(TypeError)
        result = backon.retry(
            flaky,
            backon.constant,
            condition=cond,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3


class TestNewRetryConditions:
    def test_retry_if_not_exception_type_retries_non_matching(self):
        state = RetryState(target=lambda: None)
        cond = retry_if_not_exception_type(ValueError)

        state.outcome = Attempt(exception=TypeError("type error"))
        assert cond(state) is True

        state.outcome = Attempt(exception=ValueError("value error"))
        assert cond(state) is False

    def test_retry_if_not_exception_type_with_real_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise TypeError("type fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            condition=retry_if_not_exception_type(ValueError),
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_if_not_exception_type_gives_up_on_matching(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("value fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.constant,
                condition=retry_if_not_exception_type(ValueError),
                max_tries=5,
                jitter=None,
                interval=0.01,
            )
        assert len(calls) == 1

    def test_retry_unless_exception_type_retries_non_matching(self):
        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=TypeError("type error"))
        cond = retry_unless_exception_type(ValueError)
        assert cond(state) is True

    def test_retry_unless_exception_type_does_not_retry_matching(self):
        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=ValueError("value error"))
        cond = retry_unless_exception_type(ValueError)
        assert cond(state) is False

    def test_retry_unless_exception_type_with_real_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise TypeError("type fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            condition=retry_unless_exception_type(ValueError),
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_unless_exception_type_gives_up_on_matching(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("value fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.constant,
                condition=retry_unless_exception_type(ValueError),
                max_tries=5,
                jitter=None,
                interval=0.01,
            )
        assert len(calls) == 1

    def test_retry_if_not_exception_message_no_match(self):
        cond = retry_if_not_exception_message("timeout")
        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=ValueError("everything is fine"))
        assert cond(state) is True

    def test_retry_if_not_exception_message_with_match(self):
        cond = retry_if_not_exception_message("timeout")
        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=ValueError("request timeout"))
        assert cond(state) is False

    def test_retry_if_not_exception_message_regex(self):
        cond = retry_if_not_exception_message(r"timeout|error", regex=True)
        state = RetryState(target=lambda: None)

        state.outcome = Attempt(exception=ValueError("request timeout"))
        assert cond(state) is False

        state.outcome = Attempt(exception=ValueError("unknown error"))
        assert cond(state) is False

        state.outcome = Attempt(exception=ValueError("everything is fine"))
        assert cond(state) is True

    def test_retry_if_not_exception_message_no_outcome(self):
        cond = retry_if_not_exception_message("timeout")
        state = RetryState(target=lambda: None)
        assert cond(state) is False

    def test_retry_if_not_exception_message_no_exception(self):
        cond = retry_if_not_exception_message("timeout")
        state = RetryState(target=lambda: None)
        state.outcome = Attempt()
        assert cond(state) is False

    def test_retry_if_exception_cause_type_direct_cause(self):
        try:
            try:
                raise ValueError("cause")
            except ValueError as e:
                raise RuntimeError("wrapper") from e
        except RuntimeError as e:
            state = RetryState(target=lambda: None)
            state.outcome = Attempt(exception=e)
            cond = retry_if_exception_cause_type(ValueError)
            assert cond(state) is True

    def test_retry_if_exception_cause_type_wrong_type(self):
        try:
            try:
                raise ValueError("cause")
            except ValueError as e:
                raise RuntimeError("wrapper") from e
        except RuntimeError as e:
            state = RetryState(target=lambda: None)
            state.outcome = Attempt(exception=e)
            cond = retry_if_exception_cause_type(TypeError)
            assert cond(state) is False

    def test_retry_if_exception_cause_type_no_cause(self):
        state = RetryState(target=lambda: None)
        state.outcome = Attempt(exception=ValueError("plain error"))
        cond = retry_if_exception_cause_type(TypeError)
        assert cond(state) is False

    def test_retry_if_exception_cause_type_no_exception(self):
        cond = retry_if_exception_cause_type(ValueError)
        state = RetryState(target=lambda: None)
        assert cond(state) is False

    def test_retry_if_exception_cause_type_chained_cause(self):
        try:
            try:
                try:
                    raise ValueError("deep cause")
                except ValueError as e:
                    raise TypeError("middle") from e
            except TypeError as e:
                raise RuntimeError("top") from e
        except RuntimeError as e:
            state = RetryState(target=lambda: None)
            state.outcome = Attempt(exception=e)
            cond = retry_if_exception_cause_type(ValueError)
            assert cond(state) is True

    def test_retry_if_exception_cause_type_multiple_types(self):
        try:
            try:
                raise ValueError("cause")
            except ValueError as e:
                raise RuntimeError("wrapper") from e
        except RuntimeError as e:
            state = RetryState(target=lambda: None)
            state.outcome = Attempt(exception=e)
            cond = retry_if_exception_cause_type((ValueError, TypeError))
            assert cond(state) is True

    def test_retry_if_exception_cause_type_with_real_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                try:
                    raise ValueError("cause")
                except ValueError as e:
                    raise RuntimeError("wrapper") from e
            return "ok"

        cond = retry_if_exception_cause_type(ValueError)
        result = backon.retry(
            flaky,
            backon.constant,
            condition=cond,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3


class TestNewWaitGenerators:
    def test_wait_random_values_in_range(self):
        random.seed(42)
        g = wait_random(min=1, max=2)
        for _ in range(50):
            v = g.next()
            assert 1 <= v <= 2

    def test_wait_random_min_equals_max(self):
        g = wait_random(min=5, max=5)
        for _ in range(10):
            assert g.next() == 5.0

    def test_wait_random_with_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            wait_random,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            min=0.001,
            max=0.002,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_wait_exponential_jitter_values(self):
        g = wait_exponential_jitter(initial=1, max=60, exp_base=2, jitter=0)
        assert g.next() == 2.0
        assert g.next() == 4.0
        assert g.next() == 8.0
        assert g.next() == 16.0

    def test_wait_exponential_jitter_capped_at_max(self):
        g = wait_exponential_jitter(initial=1, max=5, exp_base=2, jitter=0)
        assert g.next() == 2.0
        assert g.next() == 4.0
        assert g.next() == 5.0
        assert g.next() == 5.0

    def test_wait_exponential_jitter_with_jitter(self):
        random.seed(42)
        g = wait_exponential_jitter(initial=1, max=60, exp_base=2, jitter=1)
        for _ in range(10):
            v = g.next()
            assert v >= 2.0

    def test_wait_exponential_jitter_with_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            wait_exponential_jitter,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            initial=0.001,
            max=0.01,
            exp_base=2,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_wait_none_always_zero(self):
        g = wait_none()
        for _ in range(10):
            assert g.next() == 0.0

    def test_wait_none_with_retry(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            wait_none,
            exception=ValueError,
            max_tries=5,
        )
        assert result == "ok"
        assert len(calls) == 3


class TestWaitAddition:
    def test_wait_add_returns_combined(self):
        combined = expo + constant
        assert isinstance(combined, _CombinedWait)
        assert len(combined._waits) == 2
        assert combined._waits[0] is expo
        assert combined._waits[1] is constant

    def test_combined_wait_sums_values(self):
        combined = constant + constant
        g = combined(interval=0.05)
        result = g.next()
        assert result == pytest.approx(0.1)

    def test_combined_wait_multiple_values(self):
        combined = constant + constant
        g = combined(interval=0.05)
        assert g.next() == pytest.approx(0.1)
        assert g.next() == pytest.approx(0.1)
        assert g.next() == pytest.approx(0.1)

    def test_wait_addition_chaining(self):
        combined = expo + constant + fibo
        assert isinstance(combined, _CombinedWait)
        assert len(combined._waits) == 3
        assert combined._waits[0] is expo
        assert combined._waits[1] is constant
        assert combined._waits[2] is fibo

    def test_wait_addition_chaining_values(self):
        combined = expo + constant + fibo
        g = combined()
        result = g.next()
        assert result == pytest.approx(3.0)

    def test_combined_wait_add_chain(self):
        c1 = constant + constant
        c2 = c1 + constant
        assert isinstance(c2, _CombinedWait)
        assert len(c2._waits) == 3

    def test_combined_wait_plus_wait(self):
        c = constant + constant
        c2 = c + constant
        assert len(c2._waits) == 3

    def test_wait_add_combined_wait(self):
        c = constant + constant
        c2 = constant + c
        assert len(c2._waits) == 3


class TestToSeconds:
    def test_to_seconds_with_int(self):
        assert _to_seconds(5) == 5.0

    def test_to_seconds_with_float(self):
        assert _to_seconds(3.14) == 3.14

    def test_to_seconds_with_timedelta_seconds(self):
        assert _to_seconds(timedelta(seconds=30)) == 30.0

    def test_to_seconds_with_timedelta_minutes(self):
        assert _to_seconds(timedelta(minutes=2)) == 120.0

    def test_to_seconds_with_timedelta_hours(self):
        assert _to_seconds(timedelta(hours=1, minutes=30)) == 5400.0

    def test_to_seconds_with_timedelta_milliseconds(self):
        assert _to_seconds(timedelta(milliseconds=500)) == 0.5

    def test_to_seconds_with_zero(self):
        assert _to_seconds(0) == 0.0
        assert _to_seconds(timedelta(seconds=0)) == 0.0

    def test_to_seconds_with_negative(self):
        assert _to_seconds(-5) == -5.0
        assert _to_seconds(timedelta(seconds=-5)) == -5.0


class TestRetryingName:
    def test_name_default_is_empty(self):
        r = Retrying(constant, interval=0.01)
        assert r._name == ""

    def test_name_is_stored(self):
        r = Retrying(constant, interval=0.01, name="my-retryer")
        assert r._name == "my-retryer"

    def test_name_in_copy(self):
        r1 = Retrying(constant, interval=0.01, name="original")
        r2 = r1.copy()
        assert r2._name == "original"


class TestRetryingCopy:
    def test_copy_has_same_params(self):
        r1 = Retrying(constant, interval=0.01, max_tries=5, jitter=None, name="test")
        r2 = r1.copy()
        assert r2._wait_gen == constant
        assert r2._max_tries == 5
        assert r2._jitter is None
        assert r2._name == "test"

    def test_copy_is_independent(self):
        r1 = Retrying(constant, interval=0.01, max_tries=5, jitter=None)
        r2 = r1.copy()
        r2._max_tries = 10
        assert r1._max_tries == 5
        assert r2._max_tries == 10

    def test_copy_sleep_is_independent(self):
        def sleep1(s):
            pass

        r1 = Retrying(constant, interval=0.01, max_tries=5, jitter=None, sleep=sleep1)
        r2 = r1.copy()
        assert r2._sleep is sleep1


class TestRetryAttempt:
    def test_attempt_success(self):
        attempt = _RetryAttempt()
        with attempt:
            attempt._value = 42
        assert not attempt.failed
        assert attempt.exception is None
        assert attempt.value == 42

    def test_attempt_failure(self):
        attempt = _RetryAttempt()
        with attempt:
            raise ValueError("fail")
        assert attempt.failed
        assert isinstance(attempt.exception, ValueError)
        assert str(attempt.exception) == "fail"

    def test_attempt_value_default(self):
        attempt = _RetryAttempt()
        assert attempt.value is None

    def test_attempt_exception_default(self):
        attempt = _RetryAttempt()
        assert attempt.exception is None

    def test_attempt_failed_default(self):
        attempt = _RetryAttempt()
        assert not attempt.failed

    def test_attempt_suppresses_exception(self):
        attempt = _RetryAttempt()
        with attempt:
            raise RuntimeError("caught")
        assert attempt.failed

    def test_attempt_multiple_calls(self):
        attempt = _RetryAttempt()
        with attempt:
            attempt._value = "first"
        assert not attempt.failed
        assert attempt.value == "first"

        with attempt:
            raise KeyError("second")
        assert attempt.failed
        assert isinstance(attempt.exception, KeyError)


class TestRetryingIterator:
    def test_iterator_success_first_try(self):
        r = Retrying(expo, max_tries=3, jitter=None, sleep=lambda s: None)
        for attempt in r:
            with attempt:
                attempt._value = "ok"
        assert not attempt.failed
        assert attempt.value == "ok"

    def test_iterator_retry_then_succeed(self):
        calls = []

        r = Retrying(
            expo,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            sleep=lambda s: None,
        )
        for attempt in r:
            with attempt:
                calls.append(1)
                if len(calls) < 3:
                    raise ValueError("fail")
        assert len(calls) == 3
        assert not attempt.failed

    def test_iterator_giveup_after_max_tries(self):
        calls = []

        r = Retrying(
            expo,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            sleep=lambda s: None,
            raise_on_giveup=True,
        )
        with pytest.raises(ValueError):
            for attempt in r:
                with attempt:
                    calls.append(1)
                    raise ValueError("fail")
        assert len(calls) == 3

    def test_iterator_condition_not_met_gives_up(self):
        calls = []

        r = Retrying(
            expo,
            condition=retry_if_exception_type(TypeError),
            max_tries=5,
            jitter=None,
            sleep=lambda s: None,
            raise_on_giveup=True,
        )
        with pytest.raises(ValueError):
            for attempt in r:
                with attempt:
                    calls.append(1)
                    raise ValueError("fail")
        assert len(calls) == 1

    def test_iterator_stop_condition_works(self):
        calls = []

        r = Retrying(
            expo,
            exception=ValueError,
            stop=stop_after_attempt(2),
            jitter=None,
            sleep=lambda s: None,
            raise_on_giveup=True,
        )
        with pytest.raises(ValueError):
            for attempt in r:
                with attempt:
                    calls.append(1)
                    raise ValueError("fail")
        assert len(calls) == 2

    def test_iterator_with_constant_wait(self):
        calls = []

        r = Retrying(
            constant,
            exception=ValueError,
            max_tries=4,
            jitter=None,
            sleep=lambda s: None,
            interval=0.01,
        )
        for attempt in r:
            with attempt:
                calls.append(1)
                if len(calls) < 3:
                    raise ValueError("fail")
        assert len(calls) == 3

    def test_iterator_tracks_tries(self):
        calls = []

        r = Retrying(
            expo,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            sleep=lambda s: None,
        )
        for attempt in r:
            with attempt:
                calls.append(1)
                if len(calls) < 3:
                    raise ValueError("fail")
        assert len(calls) == 3
        assert r._iter_state.tries == 3
        assert r._iter_state.elapsed > 0


class TestAttemptResult:
    def test_attempt_result_default(self):
        ar = AttemptResult()
        assert ar.value is None
        assert ar.exception is None

    def test_attempt_result_with_value(self):
        ar = AttemptResult(value=42)
        assert ar.value == 42
        assert ar.exception is None

    def test_attempt_result_with_exception(self):
        exc = ValueError("test")
        ar = AttemptResult(exception=exc)
        assert ar.value is None
        assert ar.exception is exc

    def test_attempt_result_with_both(self):
        exc = ValueError("test")
        ar = AttemptResult(value="result", exception=exc)
        assert ar.value == "result"
        assert ar.exception is exc

    def test_attempt_result_with_none_value(self):
        ar = AttemptResult(value=None)
        assert ar.value is None
        assert ar.exception is None
