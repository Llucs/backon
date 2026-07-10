import pytest

import backon
from backon._retry._fast import _retry_fast_async, _retry_fast_sync
from backon._wait_gen import wait_none


class TestRaiseOnGiveupFastPath:
    def test_sync_returns_none_when_raise_on_giveup_false(self):
        calls = []

        @backon.on_exception(
            wait_none,
            ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
            raise_on_giveup=False,
            sleep=lambda s: None,
        )
        def f():
            calls.append(1)
            raise ValueError("boom")

        assert f() is None
        assert calls == [1, 1]

    def test_sync_raises_when_raise_on_giveup_true(self):
        @backon.on_exception(
            wait_none,
            ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
        )
        def f():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            f()

    async def test_async_returns_none_when_raise_on_giveup_false(self):
        calls = []

        @backon.on_exception(
            wait_none,
            ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
            raise_on_giveup=False,
            sleep=lambda s: None,
        )
        async def f():
            calls.append(1)
            raise ValueError("boom")

        assert await f() is None
        assert calls == [1, 1]

    async def test_async_raises_when_raise_on_giveup_true(self):
        @backon.on_exception(
            wait_none,
            ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
        )
        async def f():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await f()

    def test_fast_loop_sync_returns_none_when_raise_on_giveup_false(self):
        def boom():
            raise ValueError("boom")

        r = _retry_fast_sync(
            boom,
            wait_none,
            condition=lambda s: True,
            stop=lambda s: s.tries >= 3,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert r is None

    async def test_fast_loop_async_returns_none_when_raise_on_giveup_false(self):
        async def boom():
            raise ValueError("boom")

        r = await _retry_fast_async(
            boom,
            wait_none,
            condition=lambda s: True,
            stop=lambda s: s.tries >= 3,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert r is None


class TestFastPathSuccessPlusStop:
    def test_sync_returns_ret_when_stop_fires_on_success(self):
        calls = []

        def target():
            calls.append(1)
            return "success_value"

        r = _retry_fast_sync(
            target,
            wait_none,
            condition=lambda s: True,
            stop=lambda s: s.tries >= 1,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert r == "success_value"
        assert calls == [1]

    def test_sync_returns_ret_on_stop_iteration_after_success(self):

        class _Finite:
            def __init__(self):
                self._n = 0

            def __call__(self, **kwargs):
                return _Finite()

            def next(self, send_value=None):
                self._n += 1
                if self._n > 2:
                    raise StopIteration
                return 0.0

        def target():
            return "ok"

        r = _retry_fast_sync(
            target,
            _Finite(),
            condition=lambda s: True,
            stop=lambda s: False,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert r == "ok"

    async def test_async_returns_ret_when_stop_fires_on_success(self):
        calls = []

        async def target():
            calls.append(1)
            return "success_value"

        r = await _retry_fast_async(
            target,
            wait_none,
            condition=lambda s: True,
            stop=lambda s: s.tries >= 1,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert r == "success_value"
        assert calls == [1]

    def test_on_predicate_still_succeeds_when_max_tries_exhausted(self):
        calls = []

        @backon.on_predicate(
            backon.constant,
            predicate=lambda x: x is None,
            max_tries=3,
            interval=0.0,
            jitter=None,
            logger=None,
            sleep=lambda s: None,
        )
        def poll():
            calls.append(1)
            return None

        r = poll()
        assert r is None
        assert calls == [1, 1, 1]
