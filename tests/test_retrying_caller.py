import pytest

import backon

_KW = dict(jitter=None, interval=0.01)


class TestRetryingCaller:
    def test_retrying_caller_basic(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        caller = backon.RetryingCaller(
            backon.constant, exception=ValueError, max_tries=5, **_KW,
        )
        result = caller(flaky)
        assert result == "ok"
        assert len(calls) == 3

    def test_retrying_caller_with_on(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        caller = backon.RetryingCaller(backon.constant, max_tries=5, **_KW)
        bound = caller.on(ValueError)
        result = bound(flaky)
        assert result == "ok"
        assert len(calls) == 3

    def test_retrying_caller_copy(self):
        caller = backon.RetryingCaller(
            backon.expo, exception=ValueError, max_tries=5, jitter=None,
        )
        copied = caller.copy()
        assert copied._exception == caller._exception
        assert copied._max_tries == caller._max_tries

    def test_retrying_caller_on_returns_new_instance(self):
        caller = backon.RetryingCaller(backon.expo, max_tries=3, jitter=None)
        bound = caller.on(ValueError)
        assert bound._exception is ValueError
        assert caller._exception is None

    def test_retrying_caller_gives_up(self):
        def flaky():
            raise ValueError("always fail")

        caller = backon.RetryingCaller(
            backon.constant, exception=ValueError, max_tries=2, **_KW,
        )
        with pytest.raises(ValueError):
            caller(flaky)

    def test_retrying_caller_giveup_float(self):
        def flaky():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky, backon.constant, exception=ValueError,
                max_tries=3, jitter=None, interval=10,
                giveup=lambda e: 0.05,
            )

    @pytest.mark.asyncio
    async def test_async_retrying_caller_basic(self):
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        caller = backon.AsyncRetryingCaller(
            backon.constant, exception=ValueError, max_tries=5, **_KW,
        )
        result = await caller(flaky)
        assert result == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_async_retrying_caller_with_on(self):
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        caller = backon.AsyncRetryingCaller(backon.constant, max_tries=5, **_KW)
        bound = caller.on(ValueError)
        result = await bound(flaky)
        assert result == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_async_retrying_caller_copy(self):
        caller = backon.AsyncRetryingCaller(
            backon.expo, exception=ValueError, max_tries=5, jitter=None,
        )
        copied = caller.copy()
        assert copied._exception == caller._exception
        assert copied._max_tries == caller._max_tries
