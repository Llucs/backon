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
            return

        r = poll()
        assert r is None
        assert calls == [1, 1, 1]


class TestFastPathRetryContext:
    def test_get_attempt_number_returns_real_value_in_fast_path(self):
        collected = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
        )
        def f():
            collected.append(backon.get_attempt_number())
            raise ValueError()

        with pytest.raises(ValueError):
            f()
        assert collected == [1, 2, 3]

    def test_is_retrying_true_in_fast_path(self):
        collected = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
        )
        def f():
            collected.append(backon.is_retrying())
            raise ValueError()

        with pytest.raises(ValueError):
            f()
        assert collected == [True, True]

    def test_get_attempt_number_none_outside_retry(self):
        assert backon.get_attempt_number() is None
        assert backon.is_retrying() is False

    async def test_get_attempt_number_async_fast_path(self):
        collected = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=2,
            jitter=None,
            logger=None,
        )
        async def f():
            collected.append(backon.get_attempt_number())
            raise ValueError()

        with pytest.raises(ValueError):
            await f()
        assert collected == [1, 2]

    def test_get_attempt_number_via_retry_functional_fast_path(self):
        collected = []

        def f():
            collected.append(backon.get_attempt_number())
            raise ValueError()

        with pytest.raises(ValueError):
            backon.retry(
                f,
                backon.expo,
                exception=ValueError,
                max_tries=3,
                jitter=None,
                logger=None,
                sleep=lambda s: None,
            )
        assert collected == [1, 2, 3]


class TestFastPathIsFastPath:
    def test_before_forces_slow_path(self):
        calls = []

        def h(d):
            calls.append(1)

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            before=h,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()
        assert len(calls) >= 1

    def test_after_forces_slow_path(self):
        calls = []

        def h(d):
            calls.append(1)

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            after=h,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()
        assert len(calls) >= 1

    def test_before_sleep_alone_triggers_slow_path(self):
        calls = []

        def h(d):
            calls.append(1)

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            before_sleep=h,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()
        assert len(calls) >= 1

    def test_jitter_forces_non_fast_sync(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=backon.random_jitter,
            interval=0.01,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()

    def test_rate_limit_alone_forces_slow_path(self):
        from backon._rate_limiter import RateLimiter

        rl = RateLimiter(max_calls=1, period=0.5)
        rl.acquire()

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            rate_limit=rl,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()

    def test_on_success_forces_slow_path(self):
        calls = []

        def h(d):
            calls.append(1)

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            on_success=h,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()

    def test_on_backoff_forces_slow_path(self):
        calls = []

        def h(d):
            calls.append(1)

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            on_backoff=h,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()
        assert len(calls) >= 1

    def test_on_giveup_forces_slow_path(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            on_giveup=lambda d: None,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()

    def test_on_attempt_forces_slow_path(self):
        calls = []

        def h(d):
            calls.append(1)

        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            on_attempt=h,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            raise ValueError("x")

        with pytest.raises(ValueError):
            f()
        assert len(calls) >= 1


class TestFastPathTryAgain:
    def test_try_again_with_positive_wait_sync(self):
        calls = []

        def target():
            calls.append(1)
            if len(calls) < 2:
                raise backon.TryAgain
            return "ok"

        result = backon.retry(
            target,
            backon.constant,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            sleep=lambda s: None,
            logger=None,
        )
        assert result == "ok"
        assert len(calls) == 2

    async def test_try_again_with_positive_wait_async(self):
        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 2:
                raise backon.TryAgain
            return "ok"

        result = await backon.retry(
            target,
            backon.constant,
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0.01,
            logger=None,
        )
        assert result == "ok"
        assert len(calls) == 2


class TestFastPathRaiseOnGiveupFalse:
    def test_condition_rejects_exc_raise_on_giveup_false_sync(self):
        def target():
            raise ValueError("rejected")

        def condition(state):
            return False

        def stop(state):
            return state.tries >= 3

        result = _retry_fast_sync(
            target,
            wait_none,
            condition=condition,
            stop=stop,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert result is None

    async def test_condition_rejects_exc_raise_on_giveup_false_async(self):
        async def target():
            raise ValueError("rejected")

        result = await _retry_fast_async(
            target,
            wait_none,
            condition=lambda s: False,
            stop=lambda s: s.tries >= 3,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert result is None

    def test_wait_stop_iteration_exc_raise_on_giveup_false_sync(self):
        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.0

        def target():
            raise ValueError("fail")

        result = _retry_fast_sync(
            target,
            _OneShotWait(),
            condition=lambda s: True,
            stop=lambda s: False,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert result is None

    async def test_wait_stop_iteration_exc_raise_on_giveup_false_async(self):
        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.0

        async def target():
            raise ValueError("fail")

        result = await _retry_fast_async(
            target,
            _OneShotWait(),
            condition=lambda s: True,
            stop=lambda s: False,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
            raise_on_giveup=False,
        )
        assert result is None

    def test_wait_stop_iteration_exc_raise_on_giveup_true_sync(self):
        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.0

        def target():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            _retry_fast_sync(
                target,
                _OneShotWait(),
                condition=lambda s: True,
                stop=lambda s: False,
                jitter=None,
                max_time=None,
                wait_gen_kwargs={},
                sleep=lambda s: None,
                raise_on_giveup=True,
            )

    async def test_wait_stop_iteration_exc_raise_on_giveup_true_async(self):
        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.0

        async def target():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await _retry_fast_async(
                target,
                _OneShotWait(),
                condition=lambda s: True,
                stop=lambda s: False,
                jitter=None,
                max_time=None,
                wait_gen_kwargs={},
                sleep=lambda s: None,
                raise_on_giveup=True,
            )


class TestFastPathInnerDirect:
    def test_fast_inner_disabled(self):
        from backon._retry._fast import _retry_fast_sync_inner

        backon.disable()
        try:
            result = _retry_fast_sync_inner(lambda: 42, backon.constant)
            assert result == 42
        finally:
            backon.enable()

    def test_fast_inner_wait_gen_kwargs_none(self):
        from backon._retry._fast import _retry_fast_sync_inner

        calls = []

        def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = _retry_fast_sync_inner(
            target,
            backon.constant,
            condition=backon.retry_if_exception_type(ValueError),
            max_tries=3,
            jitter=None,
            sleep=lambda s: None,
            wait_gen_kwargs=None,
        )
        assert result == "ok"

    def test_fast_inner_stop_none_slow_path(self):
        from backon._retry._fast import _retry_fast_sync_inner

        calls = []

        def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            _retry_fast_sync_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=2,
                jitter=None,
                sleep=lambda s: None,
                on_backoff=[lambda d: None],
                wait_gen_kwargs={"interval": 0.01},
            )
        assert len(calls) == 2

    async def test_fast_inner_disabled_async(self):
        from backon._retry._fast import _retry_fast_async_inner

        backon.disable()
        try:

            async def target():
                return 42

            result = await _retry_fast_async_inner(target, backon.constant)
            assert result == 42
        finally:
            backon.enable()

    async def test_fast_inner_wait_gen_kwargs_none_async(self):
        from backon._retry._fast import _retry_fast_async_inner

        calls = []

        async def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = await _retry_fast_async_inner(
            target,
            backon.constant,
            condition=backon.retry_if_exception_type(ValueError),
            max_tries=3,
            jitter=None,
            wait_gen_kwargs=None,
        )
        assert result == "ok"

    async def test_fast_inner_stop_none_slow_path_async(self):
        from backon._retry._fast import _retry_fast_async_inner

        calls = []

        async def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await _retry_fast_async_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=2,
                jitter=None,
                on_backoff=[lambda d: None],
                wait_gen_kwargs={"interval": 0.01},
            )
        assert len(calls) == 2


class TestFastPathMore:
    def test_retry_error_callback_forces_slow_path(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            max_tries=2,
            jitter=None,
            interval=0.01,
            retry_error_callback=lambda d: None,
            sleep=lambda s: None,
            logger=None,
        )
        def f():
            return "ok"

        assert f() == "ok"

    def test_holder_forces_slow_path(self):
        from backon._retry._fast import _retry_fast_sync_inner

        calls = []

        def target():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = _retry_fast_sync_inner(
            target,
            backon.constant,
            condition=backon.retry_if_exception_type(ValueError),
            max_tries=3,
            jitter=None,
            sleep=lambda s: None,
            wait_gen_kwargs={"interval": 0.01},
            _holder={},
        )
        assert result == "ok"

    def test_try_again_stop_iteration_sync(self):
        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.01

        calls = []

        def target():
            calls.append(1)
            raise backon.TryAgain

        result = _retry_fast_sync(
            target,
            _OneShotWait(),
            condition=lambda s: True,
            stop=lambda s: False,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert result is None
        assert len(calls) == 2

    def test_try_again_stop_fires_sync(self):
        calls = []

        def target():
            calls.append(1)
            raise backon.TryAgain

        result = _retry_fast_sync(
            target,
            wait_none,
            condition=lambda s: True,
            stop=lambda s: s.tries >= 2,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert result is None
        assert len(calls) == 2

    def test_try_again_zero_wait_sync(self):
        calls = []

        def target():
            calls.append(1)
            if len(calls) < 2:
                raise backon.TryAgain
            return "ok"

        result = _retry_fast_sync(
            target,
            wait_none,
            condition=backon.retry_if_exception_type(ValueError),
            stop=lambda s: s.tries >= 3,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert result == "ok"
        assert len(calls) == 2

    def test_condition_rejects_exc_and_raises_sync(self):
        def target():
            raise ValueError("rejected")

        with pytest.raises(ValueError):
            _retry_fast_sync(
                target,
                wait_none,
                condition=lambda s: False,
                stop=lambda s: s.tries >= 3,
                jitter=None,
                max_time=None,
                wait_gen_kwargs={},
                sleep=lambda s: None,
            )

    async def test_try_again_stop_iteration_async(self):
        async def _noop(s):
            pass

        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.01

        calls = []

        async def target():
            calls.append(1)
            raise backon.TryAgain

        result = await _retry_fast_async(
            target,
            _OneShotWait(),
            condition=lambda s: True,
            stop=lambda s: False,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=_noop,
        )
        assert result is None
        assert len(calls) == 2

    async def test_try_again_stop_fires_async(self):
        calls = []

        async def target():
            calls.append(1)
            raise backon.TryAgain

        result = await _retry_fast_async(
            target,
            wait_none,
            condition=lambda s: True,
            stop=lambda s: s.tries >= 2,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert result is None
        assert len(calls) == 2

    async def test_condition_rejects_exc_and_raises_async(self):
        async def target():
            raise ValueError("rejected")

        with pytest.raises(ValueError):
            await _retry_fast_async(
                target,
                wait_none,
                condition=lambda s: False,
                stop=lambda s: s.tries >= 3,
                jitter=None,
                max_time=None,
                wait_gen_kwargs={},
                sleep=lambda s: None,
            )

    async def test_wait_stop_iteration_success_async(self):
        class _OneShotWait:
            def __init__(self):
                self._called = False

            def __call__(self, **kw):
                return _OneShotWait()

            def next(self, send=None):
                if self._called:
                    raise StopIteration
                self._called = True
                return 0.0

        calls = []

        async def target():
            calls.append(1)
            return "ok"

        result = await _retry_fast_async(
            target,
            _OneShotWait(),
            condition=lambda s: True,
            stop=lambda s: False,
            jitter=None,
            max_time=None,
            wait_gen_kwargs={},
            sleep=lambda s: None,
        )
        assert result == "ok"
        assert len(calls) == 2

    async def test_slow_path_stop_not_none_async(self):
        from backon._retry._fast import _retry_fast_async_inner

        calls = []

        async def target():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await _retry_fast_async_inner(
                target,
                backon.constant,
                condition=backon.retry_if_exception_type(ValueError),
                max_tries=2,
                jitter=None,
                on_backoff=[lambda d: None],
                wait_gen_kwargs={"interval": 0.01},
                stop=lambda s: s.tries >= 2,
            )
        assert len(calls) == 2
