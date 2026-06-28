import time

import pytest

import backon
from backon._state import RetryCallState


class TestRetryCallState:
    def test_elapsed_property(self):
        state = RetryCallState(start_time=time.monotonic())
        time.sleep(0.01)
        assert state.elapsed > 0

    def test_statistics(self):
        state = RetryCallState(
            fn=lambda: None,
            attempt_number=3,
            idle_for=2.5,
            start_time=time.monotonic(),
        )
        stats = state.statistics
        assert stats["attempt_number"] == 3
        assert stats["idle_for"] == 2.5
        assert "start_time" in stats
        assert "elapsed" in stats

    def test_to_details(self):
        state = RetryCallState(
            fn=lambda: None,
            attempt_number=3,
            start_time=time.monotonic(),
        )
        details = state.to_details()
        assert details["tries"] == 3
        assert details["target"] is state.fn

    def test_zero_start_time_elapsed(self):
        state = RetryCallState()
        assert state.elapsed == 0.0


class TestBeforeAfterHooks:
    def test_before_and_after_with_success(self):
        order = []

        def before(details):
            order.append("before")

        def after(details):
            order.append("after")

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            before=before,
            after=after,
        )
        def f():
            return "ok"

        f()
        assert order == ["before", "after"]

    def test_before_and_after_with_exception(self):
        order = []

        def before(details):
            order.append("before")

        def after(details):
            order.append("after")

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            before=before,
            after=after,
            raise_on_giveup=True,
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
        assert order == ["before", "after", "before", "after"]

    def test_before_and_after_multiple_attempts_success(self):
        calls = []
        order = []

        def before(details):
            order.append("before")

        def after(details):
            order.append("after")

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            before=before,
            after=after,
        )
        def f():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        f()
        assert order == ["before", "after", "before", "after", "before", "after"]
        assert len(calls) == 3

    def test_before_after_via_retry_functional_api(self):
        order = []
        calls = []

        def before(details):
            order.append("before")

        def after(details):
            order.append("after")

        def flaky():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            before=before,
            after=after,
        )
        assert result == "ok"
        assert order == ["before", "after", "before", "after"]

    def test_before_after_multiple_handlers(self):
        order = []

        def h1(d):
            order.append("h1")

        def h2(d):
            order.append("h2")

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            before=[h1, h2],
            after=[h2, h1],
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
        assert order == ["h1", "h2", "h2", "h1", "h1", "h2", "h2", "h1"]

    @pytest.mark.asyncio
    async def test_before_after_async(self):
        order = []

        def before(details):
            order.append("before")

        def after(details):
            order.append("after")

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            before=before,
            after=after,
        )
        async def f():
            return "ok"

        await f()
        assert order == ["before", "after"]

    @pytest.mark.asyncio
    async def test_before_after_async_exception(self):
        order = []

        def before(details):
            order.append("before")

        def after(details):
            order.append("after")

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            before=before,
            after=after,
            raise_on_giveup=True,
        )
        async def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await f()
        assert order == ["before", "after", "before", "after"]


class TestRetryingStatistics:
    def test_statistics_available_after_call(self):
        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
        )

        def flaky():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            r.call(flaky)

        stats = r.statistics
        assert "attempt_number" in stats
        assert stats["attempt_number"] == 2

    def test_statistics_before_call(self):
        r = backon.Retrying(backon.constant)
        assert r.statistics == {}

    def test_call_state_after_call(self):
        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
        )

        def flaky():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            r.call(flaky)

        cs = r.call_state
        assert cs is not None
        assert cs.attempt_number == 2

    def test_call_state_before_call(self):
        r = backon.Retrying(backon.constant)
        assert r.call_state is None

    def test_on_predicate_statistics(self):
        r = backon.Retrying(
            backon.constant,
            predicate=lambda x: x is None,
            max_tries=3,
            jitter=None,
            interval=0.01,
        )

        def flaky():
            return None

        r.call(flaky)
        stats = r.statistics
        assert "attempt_number" in stats
        assert stats["attempt_number"] == 3
