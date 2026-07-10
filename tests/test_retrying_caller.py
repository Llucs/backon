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
            backon.constant,
            exception=ValueError,
            max_tries=5,
            **_KW,
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
            backon.expo,
            exception=ValueError,
            max_tries=5,
            jitter=None,
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
            backon.constant,
            exception=ValueError,
            max_tries=2,
            **_KW,
        )
        with pytest.raises(ValueError):
            caller(flaky)

    def test_retrying_caller_giveup_float(self):
        def flaky():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.constant,
                exception=ValueError,
                max_tries=3,
                jitter=None,
                interval=10,
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
            backon.constant,
            exception=ValueError,
            max_tries=5,
            **_KW,
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
            backon.expo,
            exception=ValueError,
            max_tries=5,
            jitter=None,
        )
        copied = caller.copy()
        assert copied._exception == caller._exception
        assert copied._max_tries == caller._max_tries


class TestCallerForwardsFullOptions:
    def test_giveup_pred(self):
        attempts = []

        def flaky():
            attempts.append(1)
            raise ValueError()

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            giveup=lambda e: len(attempts) >= 2,
        )
        with pytest.raises(ValueError):
            caller(flaky)
        assert len(attempts) == 2

    def test_predicate_predicate_based(self):
        attempts = []

        def flaky():
            attempts.append(1)
            return len(attempts) >= 3

        caller = backon.RetryingCaller(
            backon.wait_none,
            predicate=lambda r: not r,
            max_tries=5,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
        )
        result = caller(flaky)
        assert result is True
        assert len(attempts) == 3

    def test_on_attempt_handler(self):
        attempts = []
        events = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError()
            return "ok"

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            on_attempt=lambda d: events.append(d["tries"]),
        )
        result = caller(flaky)
        assert result == "ok"
        assert events == [1, 2, 3]

    def test_on_giveup_handler(self):
        giveups = []

        def flaky():
            raise ValueError()

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            on_giveup=lambda d: giveups.append(d["tries"]),
            raise_on_giveup=False,
        )
        result = caller(flaky)
        assert result is None
        assert giveups == [2]

    def test_condition_and_stop(self):
        attempts = []

        def flaky():
            attempts.append(1)
            raise ValueError()

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            condition=backon.retry_if_exception_type(ValueError),
            stop=backon.stop_after_attempt(3),
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        caller(flaky)
        assert len(attempts) == 3

    def test_retry_error_callback(self):
        attempts = []
        callback_calls = []

        def flaky():
            attempts.append(1)
            raise ValueError()

        def on_giveup(d):
            callback_calls.append(d["tries"])
            return "rescued"

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            retry_error_callback=on_giveup,
        )
        result = caller(flaky)
        assert result == "rescued"
        assert callback_calls == [3]

    def test_logger_none_disables_default_logging(self):
        attempt = []

        def flaky():
            attempt.append(1)
            if len(attempt) < 2:
                raise ValueError()
            return "ok"

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
        )
        assert caller(flaky) == "ok"

    def test_raise_on_giveup_false(self):
        attempts = []

        def flaky():
            attempts.append(1)
            raise ValueError()

        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        result = caller(flaky)
        assert result is None
        assert len(attempts) == 3

    def test_copy_preserves_new_options(self):
        caller = backon.RetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            giveup=lambda e: False,
            on_attempt=lambda d: None,
            raise_on_giveup=False,
            logger=None,
        )
        copied = caller.copy()
        assert copied._giveup is caller._giveup
        assert copied._on_attempt is caller._on_attempt
        assert copied._raise_on_giveup is False

    @pytest.mark.asyncio
    async def test_async_giveup_pred(self):
        attempts = []

        async def flaky():
            attempts.append(1)
            raise ValueError()

        caller = backon.AsyncRetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            giveup=lambda e: len(attempts) >= 2,
        )
        with pytest.raises(ValueError):
            await caller(flaky)
        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_async_on_attempt_handler(self):
        attempts = []
        events = []

        async def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError()
            return "ok"

        caller = backon.AsyncRetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=5,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            on_attempt=lambda d: events.append(d["tries"]),
        )
        result = await caller(flaky)
        assert result == "ok"
        assert events == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_async_raise_on_giveup_false(self):
        attempts = []

        async def flaky():
            attempts.append(1)
            raise ValueError()

        caller = backon.AsyncRetryingCaller(
            backon.wait_none,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        result = await caller(flaky)
        assert result is None
        assert len(attempts) == 3
