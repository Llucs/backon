import pytest

import backon


class TestGlobalDisable:
    def test_disable_skips_retry(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=5, jitter=None)
        def f():
            calls.append(1)
            raise ValueError("fail")

        backon.disable()
        with pytest.raises(ValueError):
            f()
        assert len(calls) == 1

        backon.enable()

    def test_enable_after_disable(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def f():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        backon.disable()
        backon.enable()
        assert f() == "ok"
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_disable_async(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=5, jitter=None)
        async def f():
            calls.append(1)
            raise ValueError("fail")

        backon.disable()
        with pytest.raises(ValueError):
            await f()
        assert len(calls) == 1

        backon.enable()


class TestOnAttempt:
    def test_on_attempt_called(self):
        attempt_calls = []

        def handler(details):
            attempt_calls.append(details["tries"])

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_attempt=handler
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
        assert attempt_calls == [1, 2, 3]

    def test_on_attempt_success(self):
        attempt_calls = []

        def handler(details):
            attempt_calls.append(details["tries"])

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_attempt=handler
        )
        def f():
            return "ok"

        f()
        assert attempt_calls == [1]

    def test_on_attempt_predicate(self):
        attempt_calls = []

        def handler(details):
            attempt_calls.append(details["tries"])

        @backon.on_predicate(
            backon.constant, jitter=None, interval=0.01, max_tries=3, on_attempt=handler
        )
        def f():
            return None

        f()
        assert attempt_calls == [1, 2, 3]


class TestCustomSleep:
    def test_custom_sleep_called(self):
        sleep_values = []

        def fake_sleep(seconds):
            sleep_values.append(seconds)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, sleep=fake_sleep
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
        assert len(sleep_values) == 2
        assert all(v > 0 for v in sleep_values)

    def test_custom_sleep_zero(self):
        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, sleep=lambda s: None
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()

    @pytest.mark.asyncio
    async def test_custom_sleep_async(self):
        sleep_values = []

        async def fake_sleep(seconds):
            sleep_values.append(seconds)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, sleep=fake_sleep
        )
        async def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await f()
        assert len(sleep_values) == 2
