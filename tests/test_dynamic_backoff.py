import time

import pytest

import backon


def _approx_equal(a, b, tol=0.3):
    return abs(a - b) < tol


class TestDynamicBackoff:
    def test_giveup_returns_float_uses_custom_wait(self):
        call_times = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=10,
            giveup=lambda e: 0.05,
        )
        def flaky():
            call_times.append(time.monotonic())
            raise ValueError("fail")

        start = time.monotonic()
        with pytest.raises(ValueError):
            flaky()
        elapsed = time.monotonic() - start
        assert len(call_times) == 3
        assert elapsed < 1.0

    def test_giveup_returns_true_gives_up(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=5,
            jitter=None,
            interval=0.01,
            giveup=lambda e: True,
        )
        def flaky():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            flaky()
        assert len(calls) == 1

    def test_giveup_returns_false_retries_normally(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            giveup=lambda e: False,
        )
        def flaky():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            flaky()
        assert len(calls) == 3

    def test_giveup_returns_float_via_retry_function(self):
        call_times = []

        def flaky():
            call_times.append(time.monotonic())
            raise ValueError("fail")

        start = time.monotonic()
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
        elapsed = time.monotonic() - start
        assert len(call_times) == 3
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_giveup_returns_float_async(self):
        call_times = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=None,
            interval=10,
            giveup=lambda e: 0.05,
        )
        async def flaky():
            call_times.append(time.monotonic())
            raise ValueError("fail")

        start = time.monotonic()
        with pytest.raises(ValueError):
            await flaky()
        elapsed = time.monotonic() - start
        assert len(call_times) == 3
        assert elapsed < 1.0

    def test_giveup_returns_zero_retries_immediately(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=4,
            jitter=None,
            interval=10,
            giveup=lambda e: 0.0,
        )
        def flaky():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            flaky()
        assert len(calls) == 4

    def test_custom_wait_skips_wait_gen_and_jitter(self):
        wait_values = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=3,
            jitter=backon.full_jitter,
            interval=10,
            giveup=lambda e: 0.2,
        )
        def flaky():
            t = time.monotonic()
            if len(wait_values) > 0:
                wait_values.append(t - wait_values[-1])
            else:
                wait_values.append(t)
            raise ValueError("fail")

        start = time.monotonic()
        with pytest.raises(ValueError):
            flaky()
        elapsed = time.monotonic() - start
        assert len(wait_values) == 3
        assert elapsed < 1.0
