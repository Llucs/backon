import asyncio
import time

import pytest

import backon


def _on_exception(**kw):
    return backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None, **kw)


class TestAttemptTimeoutSync:
    def test_no_timeout(self):
        calls = []

        @_on_exception(attempt_timeout=None)
        def f():
            calls.append(1)
            return "ok"

        assert f() == "ok"
        assert len(calls) == 1

    def test_high_timeout_succeeds(self):
        calls = []

        @_on_exception(attempt_timeout=999)
        def f():
            calls.append(1)
            return "ok"

        assert f() == "ok"
        assert len(calls) == 1

    def test_timeout_retriggers_retry_on_exception_decorator(self):
        rl = []

        @_on_exception(attempt_timeout=0.01)
        def f():
            rl.append(1)
            time.sleep(0.5)
            return "ok"

        try:
            f()
        except Exception:
            pass
        assert len(rl) == 3

    def test_timeout_with_retry_functional(self):
        rl = []

        def f():
            rl.append(1)
            time.sleep(0.5)
            return "ok"

        try:
            backon.retry(
                f,
                backon.expo,
                max_tries=3,
                jitter=None,
                attempt_timeout=0.01,
            )
        except Exception:
            pass
        assert len(rl) == 3

    def test_timeout_with_retrying_call(self):
        rl = []

        def f():
            rl.append(1)
            time.sleep(0.5)
            return "ok"

        r = backon.Retrying(
            backon.expo,
            max_tries=3,
            jitter=None,
            attempt_timeout=0.01,
        )
        try:
            r.call(f)
        except Exception:
            pass
        assert len(rl) == 3

    def test_timeout_with_retrying_caller(self):
        rl = []

        def f():
            rl.append(1)
            time.sleep(0.5)
            return "ok"

        caller = backon.RetryingCaller(
            backon.expo,
            max_tries=3,
            jitter=None,
            attempt_timeout=0.01,
        )
        try:
            caller(f)
        except Exception:
            pass
        assert len(rl) == 3


class TestAttemptTimeoutAsync:
    @pytest.mark.asyncio
    async def test_no_timeout_async(self):
        calls = []

        @_on_exception(attempt_timeout=None)
        async def f():
            calls.append(1)
            return "ok"

        assert await f() == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_high_timeout_succeeds_async(self):
        calls = []

        @_on_exception(attempt_timeout=999)
        async def f():
            calls.append(1)
            return "ok"

        assert await f() == "ok"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry_async_decorator(self):
        rl = []

        @_on_exception(attempt_timeout=0.01)
        async def f():
            rl.append(1)
            await asyncio.sleep(0.5)
            return "ok"

        try:
            await f()
        except Exception:
            pass
        assert len(rl) == 3

    @pytest.mark.asyncio
    async def test_timeout_with_retry_functional_async(self):
        rl = []

        async def f():
            rl.append(1)
            await asyncio.sleep(0.5)
            return "ok"

        try:
            await backon.retry(
                f,
                backon.expo,
                max_tries=3,
                jitter=None,
                attempt_timeout=0.01,
            )
        except Exception:
            pass
        assert len(rl) == 3

    @pytest.mark.asyncio
    async def test_timeout_with_retrying_async_call(self):
        rl = []

        async def f():
            rl.append(1)
            await asyncio.sleep(0.5)
            return "ok"

        r = backon.Retrying(
            backon.expo,
            max_tries=3,
            jitter=None,
            attempt_timeout=0.01,
        )
        try:
            await r.async_call(f)
        except Exception:
            pass
        assert len(rl) == 3

    @pytest.mark.asyncio
    async def test_timeout_with_async_retrying_caller(self):
        rl = []

        async def f():
            rl.append(1)
            await asyncio.sleep(0.5)
            return "ok"

        caller = backon.AsyncRetryingCaller(
            backon.expo,
            max_tries=3,
            jitter=None,
            attempt_timeout=0.01,
        )
        try:
            await caller(f)
        except Exception:
            pass
        assert len(rl) == 3
