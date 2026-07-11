import asyncio

import pytest

import backon
from backon import HedgeError, HedgingRetrying, hedge, on_hedge
from backon._wait_gen import wait_none


class TestHedgeSync:
    def test_hedge_returns_first_success(self):
        def target():
            return "ok"

        result = hedge(target, wait_none, max_hedge=3, max_tries=1, jitter=None)
        assert result == "ok"

    def test_hedge_raises_when_all_attempts_fail(self):
        def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            hedge(boom, wait_none, max_hedge=2, max_tries=3, jitter=None)

    def test_hedge_with_exception_filter_raises(self):
        def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            hedge(
                boom,
                wait_none,
                max_hedge=2,
                max_tries=3,
                exception=ValueError,
                jitter=None,
            )

    def test_hedge_with_non_matching_exception_propagates_original(self):
        def boom():
            raise KeyError("boom")

        with pytest.raises(KeyError):
            hedge(
                boom,
                wait_none,
                max_hedge=2,
                max_tries=3,
                exception=ValueError,
                jitter=None,
            )

    def test_hedge_max_hedge_one(self):
        calls = []

        def target():
            calls.append(1)
            return "ok"

        result = hedge(target, wait_none, max_hedge=1, max_tries=1, jitter=None)
        assert result == "ok"

    def test_hedge_returns_real_value_not_none_on_failure(self):
        def boom():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            hedge(boom, wait_none, max_hedge=2, max_tries=2, jitter=None)


class TestHedgeAsync:
    def test_hedge_async_returns_first_success(self):
        async def target():
            return "ok"

        result = asyncio.run(
            hedge(target, wait_none, max_hedge=3, max_tries=1, jitter=None)
        )
        assert result == "ok"

    def test_hedge_async_raises_when_all_attempts_fail(self):
        async def boom():
            raise ValueError("aboom")

        with pytest.raises(ValueError, match="aboom"):
            asyncio.run(
                hedge(
                    boom,
                    wait_none,
                    max_hedge=2,
                    max_tries=3,
                    exception=ValueError,
                    jitter=None,
                )
            )

    def test_hedge_async_with_exception_filter_raises(self):
        async def boom():
            raise ValueError("aboom")

        with pytest.raises(ValueError):
            asyncio.run(
                hedge(
                    boom,
                    wait_none,
                    max_hedge=2,
                    max_tries=3,
                    exception=ValueError,
                    jitter=None,
                )
            )


class TestOnHedgeDecorator:
    def test_on_hedge_returns_value(self):
        @on_hedge(wait_none, max_hedge=2, max_tries=1, jitter=None)
        def target():
            return "ok"

        assert target() == "ok"

    def test_on_hedge_raises_on_full_failure(self):
        @on_hedge(wait_none, max_hedge=2, max_tries=2, jitter=None)
        def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            boom()

    def test_on_hedge_fires_callback(self):
        fired = []

        @on_hedge(
            wait_none,
            max_hedge=3,
            max_tries=1,
            jitter=None,
            on_hedge=lambda d: fired.append(d["hedge_count"]),
        )
        def target():
            return "ok"

        target()
        assert fired == [3]


class TestHedgingRetrying:
    def test_call_returns_value(self):
        with HedgingRetrying(wait_none, max_hedge=2, max_tries=1, jitter=None) as h:
            assert h.call(lambda: "ok") == "ok"

    def test_call_raises_on_full_failure(self):
        with HedgingRetrying(wait_none, max_hedge=2, max_tries=2, jitter=None) as h:

            def boom():
                raise ValueError("boom")

            with pytest.raises(ValueError):
                h.call(boom)

    def test_async_call_returns_value(self):
        async def main():
            with HedgingRetrying(wait_none, max_hedge=2, max_tries=1, jitter=None) as h:

                async def target():
                    return "ok"

                return await h.async_call(target)

        assert asyncio.run(main()) == "ok"


class TestHedgeEdgeCases:
    def test_hedge_no_max_tries_uses_default_condition(self):
        calls = []

        def boom():
            calls.append(1)
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            hedge(
                boom,
                wait_none,
                max_hedge=1,
                max_tries=1,
                exception=ValueError,
                jitter=None,
            )
        assert len(calls) == 1

    def test_hedge_predicate_path_does_not_crash(self):
        calls = []

        def target():
            calls.append(1)
            return

        result = hedge(
            target,
            wait_none,
            max_hedge=1,
            max_tries=2,
            predicate=lambda x: x is None,
            jitter=None,
        )
        assert result is None

    def test_hedge_constant_returns_value(self):
        result = hedge(
            lambda: "ok",
            backon.constant,
            max_hedge=1,
            max_tries=1,
            interval=0.0,
            jitter=None,
        )
        assert result == "ok"


def test_hedge_error_exported():
    assert HedgeError is backon.HedgeError
