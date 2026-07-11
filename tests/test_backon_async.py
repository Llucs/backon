import pytest

import backon


class TestAsyncOnException:
    @pytest.mark.asyncio
    async def test_success(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3)
        async def f():
            calls.append(1)
            return "ok"

        assert await f() == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        async def f():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("retry")
            return "ok"

        assert await f() == "ok"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_giveup_after_max_tries(self):
        calls = []

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, raise_on_giveup=True
        )
        async def f():
            calls.append(1)
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            await f()
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_raise_on_giveup_false(self):
        calls = []

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, raise_on_giveup=False
        )
        async def f():
            calls.append(1)
            raise ValueError("always fail")

        assert await f() is None
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_giveup_condition(self):
        calls = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=5,
            jitter=None,
            giveup=lambda e: "fatal" in str(e),
        )
        async def f():
            calls.append(1)
            raise ValueError("fatal error")

        with pytest.raises(ValueError):
            await f()
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_on_backoff_handler(self):
        handler_calls = []

        async def handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_backoff=handler
        )
        async def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await f()
        assert len(handler_calls) == 2

    @pytest.mark.asyncio
    async def test_on_success_handler(self):
        handler_calls = []

        async def handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_success=handler
        )
        async def f():
            return "ok"

        await f()
        assert len(handler_calls) == 1

    @pytest.mark.asyncio
    async def test_on_giveup_handler(self):
        handler_calls = []

        async def handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_giveup=handler
        )
        async def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await f()
        assert len(handler_calls) == 1

    @pytest.mark.asyncio
    async def test_sync_handler_wrapped(self):
        handler_calls = []

        def sync_handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_backoff=sync_handler
        )
        async def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await f()
        assert len(handler_calls) == 2

    @pytest.mark.asyncio
    async def test_max_time_async(self):
        @backon.on_exception(
            backon.expo, ValueError, max_time=0.1, jitter=None, raise_on_giveup=True
        )
        async def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await f()


class TestAsyncOnPredicate:
    @pytest.mark.asyncio
    async def test_retry_on_falsey(self):
        calls = []

        @backon.on_predicate(backon.constant, jitter=None, interval=0.01, max_tries=3)
        async def f():
            calls.append(1)
            return

        assert await f() is None
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_success_on_truthy(self):
        calls = []

        @backon.on_predicate(backon.constant, jitter=None, interval=0.01, max_tries=3)
        async def f():
            calls.append(1)
            return "ok"

        assert await f() == "ok"
        assert len(calls) == 1
