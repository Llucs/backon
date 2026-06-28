import pytest

import backon


class TestRetryFunction:
    def test_retry_on_exception_sync(self):
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

    def test_retry_on_predicate_sync(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                return None
            return "ok"

        result = backon.retry(
            flaky,
            backon.constant,
            predicate=lambda x: x is None,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    def test_retry_giveup_raises(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.expo,
                exception=ValueError,
                max_tries=2,
                jitter=None,
            )
        assert len(calls) == 2

    def test_retry_disabled(self):
        calls = []

        def flaky():
            calls.append(1)
            raise ValueError("fail")

        backon.disable()
        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.expo,
                exception=ValueError,
                max_tries=5,
                jitter=None,
            )
        assert len(calls) == 1
        backon.enable()

    @pytest.mark.asyncio
    async def test_retry_on_exception_async(self):
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = await backon.retry(
            flaky,
            backon.constant,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_retry_on_predicate_async(self):
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                return None
            return "ok"

        result = await backon.retry(
            flaky,
            backon.constant,
            predicate=lambda x: x is None,
            max_tries=5,
            jitter=None,
            interval=0.01,
        )
        assert result == "ok"
        assert len(calls) == 3


class TestRetryingContextManager:
    def test_retrying_sync_exception(self):
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
            jitter=None,
            interval=0.01,
        ) as r:
            result = r.call(flaky)

        assert result == "ok"
        assert len(calls) == 3

    def test_retrying_sync_predicate(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                return None
            return "ok"

        with backon.Retrying(
            backon.constant,
            predicate=lambda x: x is None,
            max_tries=5,
            jitter=None,
            interval=0.01,
        ) as r:
            result = r.call(flaky)

        assert result == "ok"
        assert len(calls) == 3

    def test_retrying_giveup_raises(self):
        def flaky():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            with backon.Retrying(
                backon.expo,
                exception=ValueError,
                max_tries=2,
                jitter=None,
            ) as r:
                r.call(flaky)

    @pytest.mark.asyncio
    async def test_retrying_async(self):
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        async with backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
        ) as r:
            result = await r.async_call(flaky)

        assert result == "ok"
        assert len(calls) == 3
