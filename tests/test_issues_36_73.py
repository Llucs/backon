import contextlib
import threading
import time

import pytest

import backon


def _wait_for_thread_baseline(baseline, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if threading.active_count() <= baseline:
            break
        time.sleep(0.01)
    return threading.active_count() <= baseline


class TestIssue36ExecutorLeak:
    def test_no_thread_leak_on_exception_path(self):
        baseline = threading.active_count()

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=4,
            interval=0,
            jitter=None,
            attempt_timeout=5.0,
        )
        def fn():
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            fn()

        assert _wait_for_thread_baseline(baseline)

    def test_no_thread_leak_on_exception_path_functional_api(self):
        baseline = threading.active_count()

        def fn():
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            backon.retry(
                fn,
                backon.constant,
                exception=ValueError,
                max_tries=4,
                interval=0,
                jitter=None,
                attempt_timeout=5.0,
            )

        assert _wait_for_thread_baseline(baseline)

    def test_no_thread_leak_on_exception_path_retrying_caller(self):
        baseline = threading.active_count()

        def fn():
            raise ValueError("fail")

        caller = backon.RetryingCaller(
            backon.constant,
            max_tries=4,
            jitter=None,
            interval=0,
            attempt_timeout=5.0,
        )
        caller = caller.on(ValueError)
        with contextlib.suppress(ValueError):
            caller(fn)

        assert _wait_for_thread_baseline(baseline)

    def test_no_thread_leak_on_success_path(self):
        baseline = threading.active_count()
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            interval=0,
            jitter=None,
            attempt_timeout=5.0,
        )
        def fn():
            calls.append(1)
            return "ok"

        assert fn() == "ok"
        assert len(calls) == 1

        assert _wait_for_thread_baseline(baseline)


class TestIssue73HandlerDetailsArgs:
    def test_on_exception_backoff_receives_kwargs(self):
        seen = []

        def handler(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            interval=0,
            jitter=None,
            on_backoff=handler,
        )
        def do_something(num, *, query_id, flag=True):
            raise ValueError("boom")

        with contextlib.suppress(ValueError):
            do_something(42, query_id=7, flag=False)

        assert len(seen) == 2
        assert all(
            args == (42,) and kw == {"query_id": 7, "flag": False} for args, kw in seen
        )

    def test_on_exception_giveup_and_attempt_receive_args(self):
        events = []

        def on_attempt(details):
            events.append(("attempt", details["args"], dict(details["kwargs"])))

        def on_giveup(details):
            events.append(("giveup", details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            interval=0,
            jitter=None,
            on_attempt=on_attempt,
            on_giveup=on_giveup,
        )
        def flaky(x, y=0):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            flaky(1, y=2)

        assert ("attempt", (1,), {"y": 2}) in events
        assert ("giveup", (1,), {"y": 2}) in events

    def test_on_predicate_success_receives_args(self):
        seen = []

        def on_success(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_predicate(
            backon.constant,
            lambda v: v != "ok",
            max_tries=3,
            interval=0,
            jitter=None,
            on_success=on_success,
        )
        def fetch(key, *, source="db"):
            return "ok"

        assert fetch("user", source="cache") == "ok"
        assert seen == [(("user",), {"source": "cache"})]

    def test_on_predicate_backoff_receives_args(self):
        seen = []
        calls = []

        def on_backoff(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_predicate(
            backon.constant,
            lambda v: v != "ok",
            max_tries=3,
            interval=0,
            jitter=None,
            on_backoff=on_backoff,
        )
        def fetch(key):
            calls.append(key)
            return "ok" if len(calls) > 1 else "retry"

        assert fetch("user") == "ok"
        assert seen == [(("user",), {})]

    def test_before_sleep_receives_args(self):
        seen = []

        def before_sleep(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            interval=0,
            jitter=None,
            before_sleep=before_sleep,
        )
        def fn(a, *, b=0):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            fn(1, b=2)

        assert len(seen) == 2
        assert all(s == ((1,), {"b": 2}) for s in seen)

    def test_before_and_after_receives_args(self):
        seen = []

        def before(details):
            seen.append(("before", details["args"], dict(details["kwargs"])))

        def after(details):
            seen.append(("after", details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            interval=0,
            jitter=None,
            before=before,
            after=after,
        )
        def fn(a):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            fn("x")

        assert ("before", ("x",), {}) in seen
        assert ("after", ("x",), {}) in seen

    @pytest.mark.asyncio
    async def test_async_on_exception_backoff_receives_kwargs(self):
        seen = []

        def handler(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            interval=0,
            jitter=None,
            on_backoff=handler,
        )
        async def do_something(query_id):
            raise ValueError("boom")

        with contextlib.suppress(ValueError):
            await do_something(query_id=42)

        assert len(seen) == 2
        assert all(args == () and kw == {"query_id": 42} for args, kw in seen)

    @pytest.mark.asyncio
    async def test_async_on_predicate_success_receives_args(self):
        seen = []

        def on_success(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_predicate(
            backon.constant,
            lambda v: v != "ok",
            max_tries=3,
            interval=0,
            jitter=None,
            on_success=on_success,
        )
        async def fetch(key, *, source="db"):
            return "ok"

        assert await fetch("user", source="cache") == "ok"
        assert seen == [(("user",), {"source": "cache"})]

    def test_retrying_call_state_populates_args_kwargs(self):
        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            interval=0,
            jitter=None,
        )

        def flaky(x, *, y=0):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            r.call(flaky, 1, y=2)

        cs = r.call_state
        assert cs is not None
        assert cs.args == (1,)
        assert cs.kwargs == {"y": 2}

    def test_retrying_caller_handler_receives_args(self):
        seen = []

        def on_backoff(details):
            seen.append((details["args"], dict(details["kwargs"])))

        caller = backon.RetryingCaller(
            backon.constant,
            max_tries=3,
            jitter=None,
            interval=0,
            on_backoff=on_backoff,
        )
        caller = caller.on(ValueError)

        def flaky(x, *, y=0):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            caller(flaky, 1, y=2)

        assert len(seen) == 2
        assert all(s == ((1,), {"y": 2}) for s in seen)

    @pytest.mark.asyncio
    async def test_async_retrying_call_state_populates_args(self):
        r = backon.Retrying(
            backon.constant,
            exception=ValueError,
            max_tries=2,
            interval=0,
            jitter=None,
        )

        async def flaky(x, *, y=0):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            at = r.async_call(flaky, 1, y=2)
            await at

        cs = r.call_state
        assert cs is not None
        assert cs.args == (1,)
        assert cs.kwargs == {"y": 2}

    @pytest.mark.asyncio
    async def test_async_retrying_caller_handler_receives_args(self):
        seen = []

        def on_backoff(details):
            seen.append((details["args"], dict(details["kwargs"])))

        caller = backon.AsyncRetryingCaller(
            backon.constant,
            max_tries=3,
            jitter=None,
            interval=0,
            on_backoff=on_backoff,
        )
        caller = caller.on(ValueError)

        async def flaky(x, *, y=0):
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            await caller(flaky, 1, y=2)

        assert len(seen) == 2
        assert all(s == ((1,), {"y": 2}) for s in seen)

    def test_on_exception_handler_keyerror_regression(self):
        captured = {}

        def handler(details):
            captured["query_id"] = details["kwargs"]["query_id"]

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            interval=0,
            jitter=None,
            on_backoff=handler,
        )
        def do_something(query_id):
            raise ValueError("boom")

        with contextlib.suppress(ValueError):
            do_something(query_id=42)

        assert captured == {"query_id": 42}


class TestIssue73GeneratorHandlerDetailsArgs:
    def test_sync_generator_handler_receives_args(self):
        seen = []

        def on_backoff(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            interval=0,
            jitter=None,
            on_backoff=on_backoff,
        )
        def gen(x, *, y=0):
            yield 1
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            list(gen(5, y=9))

        assert len(seen) == 2
        assert all(s == ((5,), {"y": 9}) for s in seen)

    @pytest.mark.asyncio
    async def test_async_generator_handler_receives_args(self):
        seen = []

        def on_backoff(details):
            seen.append((details["args"], dict(details["kwargs"])))

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            interval=0,
            jitter=None,
            on_backoff=on_backoff,
        )
        async def gen(x, *, y=0):
            yield 1
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            results = []
            async for item in gen(5, y=9):
                results.append(item)

        assert len(seen) == 2
        assert all(s == ((5,), {"y": 9}) for s in seen)
