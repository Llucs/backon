import pytest

import backon


class TestCoverageGaps:
    def test_retry_with_default_jitter(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        with backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=5,
            interval=0.01,
        ) as r:
            result = r.call(flaky)
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_stop_never_with_condition(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.constant,
                exception=ValueError,
                jitter=None,
                condition=backon.retry_never(),
                interval=0.01,
            )
        assert len(calls) == 1

    def test_retry_with_condition_returning_float_on_success(self):
        calls = []

        def condition(state):
            if (
                state.outcome
                and not state.outcome.exception
                and state.outcome.value < 3
            ):
                return 0.01
            return False

        def flaky():
            calls.append(1)
            return len(calls)

        with backon.Retrying(
            backon.constant,
            condition=condition,
            max_tries=5,
            jitter=None,
            interval=0.01,
        ) as r:
            result = r.call(flaky)
        assert result == 3
        assert len(calls) == 3

    def test_retry_with_sequence_exception(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise TypeError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            exception=(ValueError, TypeError),
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_with_max_time(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            exception=ValueError,
            max_tries=5,
            max_time=10.0,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_with_giveup_none(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_giveup_with_backoff_details(self):
        details = {}

        def on_backoff(d):
            details.update(d)

        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            on_backoff=on_backoff,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retrying_call_async_raise_typeerror(self):
        async def async_fn():
            return 42

        retrying = backon.Retrying(
            backon.constant, exception=ValueError, jitter=None, interval=0.01
        )
        with pytest.raises(TypeError):
            retrying.call(async_fn)

    def test_retrying_statistics_after_call(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        r.call(flaky)
        stats = r.statistics
        assert stats["attempt_number"] == 3

    def test_retrying_iterator_giveup(self):
        attempts = []
        for attempt in backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            raise_on_giveup=False,
            interval=0.01,
        ):
            with attempt:
                raise ValueError("fail")
            attempts.append(attempt)
        assert len(attempts) == 2
        assert attempts[0].failed
        assert attempts[1].failed
