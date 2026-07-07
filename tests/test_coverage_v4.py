from __future__ import annotations

import pytest

import backon
from backon._conditions import RetryCondition
from backon._retry._helpers import _make_default_condition
from backon._state import Attempt, RetryState


class TestOnPredicateAsyncGenerator:
    """Covers async generator branch in on_predicate."""

    @pytest.mark.asyncio
    async def test_async_generator_success(self):
        calls = []

        @backon.on_predicate(backon.constant, interval=0, jitter=None)
        async def gen():
            calls.append(1)
            yield 10
            yield 20

        result = [item async for item in gen()]
        assert result == [10, 20]
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_async_generator_predicate_retry(self):
        calls = []

        @backon.on_predicate(
            backon.constant,
            interval=0,
            jitter=None,
            max_tries=3,
            predicate=lambda x: not x,
        )
        async def gen():
            calls.append(1)
            if len(calls) < 2:
                return
            yield 99

        result = [item async for item in gen()]
        assert result == [99]
        assert len(calls) == 2


class TestOnPredicateSyncGeneratorDisabled:
    """Covers disabled branch in on_predicate sync generator."""

    def test_sync_generator_disabled_then_enabled(self):
        was = backon._common.is_enabled()
        backon.disable()
        try:
            calls = []

            @backon.on_predicate(backon.constant, interval=0, jitter=None)
            def gen():
                calls.append(1)
                yield "a"
                yield "b"

            result = list(gen())
            assert result == ["a", "b"]
            assert len(calls) == 1
        finally:
            if was:
                backon.enable()


class TestOnExceptionGiveupNotNone:
    """Covers giveup not None branch in on_exception."""

    def test_giveup_returns_true_no_retry(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=3,
            giveup=lambda e: True,
        )
        def fn():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(calls) == 1

    def test_giveup_returns_false_retries(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=3,
            giveup=lambda e: False,
        )
        def fn():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        assert fn() == "ok"
        assert len(calls) == 2


class TestOnExceptionAsyncGeneratorDisabled:
    """Covers disabled branch in on_exception async generator."""

    @pytest.mark.asyncio
    async def test_async_generator_disabled_then_enabled(self):
        was = backon._common.is_enabled()
        backon.disable()
        try:
            calls = []

            @backon.on_exception(backon.constant, ValueError, interval=0, jitter=None)
            async def gen():
                calls.append(1)
                yield "x"
                raise ValueError("boom")

            with pytest.raises(ValueError):
                async for _ in gen():
                    pass
            assert len(calls) == 1
        finally:
            if was:
                backon.enable()


class TestOnExceptionSyncGeneratorDisabled:
    """Covers disabled branch in on_exception sync generator."""

    def test_sync_generator_disabled_then_enabled(self):
        was = backon._common.is_enabled()
        backon.disable()
        try:
            calls = []

            @backon.on_exception(backon.constant, ValueError, interval=0, jitter=None)
            def gen():
                calls.append(1)
                yield "y"
                raise ValueError("boom")

            with pytest.raises(ValueError):
                list(gen())
            assert len(calls) == 1
        finally:
            if was:
                backon.enable()


class TestRetryWithUnknownKwargs:
    """Covers unknown-kwargs branch in retry_with."""

    def test_on_exception_retry_with_unknown_kwarg(self):
        @backon.on_exception(
            backon.constant, ValueError, max_tries=2, interval=0, jitter=None
        )
        def fn():
            raise ValueError("fail")

        wrapped = fn.retry_with(some_unknown_kwarg=42)
        with pytest.raises(TypeError):
            wrapped()

    def test_on_predicate_retry_with_unknown_kwarg(self):
        @backon.on_predicate(backon.constant, max_tries=2, interval=0, jitter=None)
        def fn():
            return None

        wrapped = fn.retry_with(some_unknown_kwarg=42)
        with pytest.raises(TypeError):
            wrapped()


class TestConfigHandlersLoggerAndUserHandlers:
    """Covers _config_handlers logger + user handlers."""

    def test_on_backoff_handler_with_default_logger(self):
        handler_calls = []

        def my_handler(details):
            handler_calls.append(details["tries"])

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=3,
            on_backoff=my_handler,
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(handler_calls) == 2

    def test_on_giveup_handler_with_default_logger(self):
        handler_calls = []

        def my_handler(details):
            handler_calls.append(details["tries"])

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            on_giveup=my_handler,
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(handler_calls) == 1


class TestConfigHandlersNoLoggerSingleHandler:
    """Covers _config_handlers logger None + single handler."""

    def test_on_success_single_callable_handler(self):
        handler_calls = []

        def my_handler(details):
            handler_calls.append(details["tries"])

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=3,
            on_success=my_handler,
        )
        def fn():
            return "ok"

        assert fn() == "ok"
        assert len(handler_calls) == 1

    def test_on_attempt_single_callable_handler(self):
        handler_calls = []

        def my_handler(details):
            handler_calls.append(details["tries"])

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            on_attempt=my_handler,
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(handler_calls) == 2


class TestCustomWaitOnSuccessPath:
    """Covers custom wait on SUCCESS path in _decide_outcome."""

    def test_condition_returns_float_on_success_retries(self):
        class _FloatOnSuccess(RetryCondition):
            def __call__(self, state):
                return 0.0

        calls = []

        def fn():
            calls.append(1)
            return "ok"

        result = backon.retry(
            fn,
            backon.constant,
            condition=_FloatOnSuccess(),
            max_tries=3,
            jitter=None,
            sleep=lambda s: None,
        )
        assert result == "ok"
        assert len(calls) == 3


class TestCustomWaitOnExceptionPath:
    """Covers custom wait on EXCEPTION path (retry_if_exception float)."""

    def test_retry_if_exception_returns_float(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            fn,
            backon.constant,
            condition=backon.retry_if_exception(lambda e: 0.0),
            max_tries=4,
            jitter=None,
            sleep=lambda s: None,
        )
        assert result == "ok"
        assert len(calls) == 3


class TestExceptionAsSequence:
    """Covers tuple(exception) in _helpers.py:33-36 and _decorator.py:404-408."""

    def test_on_exception_with_tuple(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            (ValueError, TypeError),
            interval=0,
            jitter=None,
            max_tries=2,
        )
        def fn():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(calls) == 2

    def test_make_default_condition_with_tuple(self):
        condition = _make_default_condition(
            exception=(ValueError, TypeError),
            giveup=None,
            predicate=lambda x: False,
        )
        state = RetryState()
        state.outcome = Attempt(exception=ValueError("fail"))
        assert condition(state) is True

        state2 = RetryState()
        state2.outcome = Attempt(exception=RuntimeError("nope"))
        assert condition(state2) is False

    def test_retry_function_with_tuple_exception(self):
        calls = []

        def fn():
            calls.append(1)
            raise TypeError("bad type")

        with pytest.raises(TypeError):
            backon.retry(
                fn,
                backon.constant,
                exception=(ValueError, TypeError),
                max_tries=3,
                jitter=None,
                interval=0,
                sleep=lambda s: None,
            )
        assert len(calls) == 3


class TestCustomJitterInNextWait:
    """Covers jitter function call in _next_wait."""

    def test_custom_jitter_called_on_retry(self):
        jitter_calls = []

        def custom_jitter(value):
            jitter_calls.append(value)
            return value * 2

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=custom_jitter,
            max_tries=3,
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(jitter_calls) > 0
        assert all(v == 0 for v in jitter_calls)


class TestConfigHandlersNoLoggerIterableHandlers:
    """Covers _config_handlers logger None + tuple handlers.

    Using a tuple (not list) because a list is short-circuited at line 98-99.
    """

    def test_on_success_tuple_of_handlers(self):
        handler_calls = []

        def h1(d):
            handler_calls.append(1)

        def h2(d):
            handler_calls.append(2)

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            on_success=(h1, h2),
        )
        def fn():
            return "ok"

        assert fn() == "ok"
        assert handler_calls == [1, 2]

    def test_on_attempt_tuple_of_handlers(self):
        handler_calls = []

        def h1(d):
            handler_calls.append(1)

        def h2(d):
            handler_calls.append(2)

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            on_attempt=(h1, h2),
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert handler_calls == [1, 2, 1, 2]

    def test_before_sleep_tuple_of_handlers(self):
        handler_calls = []

        def h1(d):
            handler_calls.append(1)

        def h2(d):
            handler_calls.append(2)

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            before_sleep=(h1, h2),
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert handler_calls == [1, 2]

    def test_before_tuple_of_handlers(self):
        handler_calls = []

        def h1(d):
            handler_calls.append(1)

        def h2(d):
            handler_calls.append(2)

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            before=(h1, h2),
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert handler_calls == [1, 2, 1, 2]

    def test_after_tuple_of_handlers(self):
        handler_calls = []

        def h1(d):
            handler_calls.append(1)

        def h2(d):
            handler_calls.append(2)

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            after=(h1, h2),
        )
        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert handler_calls == [1, 2, 1, 2]


class TestOnPredicateAsyncGeneratorDisabledPath:
    """Covers disabled branch for async gen in on_predicate."""

    @pytest.mark.asyncio
    async def test_async_generator_disabled(self):
        was = backon._common.is_enabled()
        backon.disable()
        try:
            calls = []

            @backon.on_predicate(backon.constant, interval=0, jitter=None)
            async def gen():
                calls.append(1)
                yield "x"
                yield "y"

            result = [item async for item in gen()]
            assert result == ["x", "y"]
            assert len(calls) == 1
        finally:
            if was:
                backon.enable()


class TestGiveupReturnsTruthyString:
    """Covers giveup returning non-bool non-float truthy value."""

    def test_giveup_returns_string_triggers_retry(self):
        calls = []

        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=3,
            giveup=lambda e: "yes",
        )
        def fn():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            fn()
        assert len(calls) == 3


class TestOnPredicateSyncGeneratorCollectedNone:
    """Covers collected None in on_predicate sync gen (retry returns None)."""

    def test_sync_generator_raises_returns_none_on_giveup(self):
        @backon.on_predicate(
            backon.constant,
            interval=0,
            jitter=None,
            max_tries=2,
            predicate=lambda x: True,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        def gen():
            yield 1
            raise ValueError("predicate-exc")

        result = list(gen())
        assert result == []


class TestOnPredicateAsyncGeneratorCollectedNone:
    """Covers collected None in on_predicate async gen."""

    @pytest.mark.asyncio
    async def test_async_generator_raises_returns_none_on_giveup(self):
        @backon.on_predicate(
            backon.constant,
            interval=0,
            jitter=None,
            max_tries=2,
            predicate=lambda x: True,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        async def gen():
            yield 1
            raise ValueError("predicate-exc")

        result = [item async for item in gen()]
        assert result == []


class TestOnExceptionSyncGeneratorCollectedNone:
    """Covers collected None in on_exception sync gen."""

    def test_sync_generator_exception_returns_none_on_giveup(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        def gen():
            yield 1
            raise ValueError("boom")

        result = list(gen())
        assert result == []


class TestOnExceptionAsyncGeneratorCollectedNone:
    """Covers collected None in on_exception async gen."""

    @pytest.mark.asyncio
    async def test_async_generator_exception_returns_none_on_giveup(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        async def gen():
            yield 1
            raise ValueError("boom")

        result = [item async for item in gen()]
        assert result == []


class TestCollectedNoneNonGenerator:
    """Covers retry inner returning None."""

    def test_sync_predicate_none_returned(self):
        @backon.on_predicate(
            backon.constant,
            interval=0,
            jitter=None,
            max_tries=2,
            predicate=lambda x: True,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        def fn():
            return None

        assert fn() is None

    def test_sync_exception_none_returned(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        def fn():
            raise ValueError("fail")

        assert fn() is None

    @pytest.mark.asyncio
    async def test_async_predicate_none_returned(self):
        @backon.on_predicate(
            backon.constant,
            interval=0,
            jitter=None,
            max_tries=2,
            predicate=lambda x: True,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        async def fn():
            return None

        result = await fn()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_exception_none_returned(self):
        @backon.on_exception(
            backon.constant,
            ValueError,
            interval=0,
            jitter=None,
            max_tries=2,
            raise_on_giveup=False,
            retry_error_callback=lambda d: None,
        )
        async def fn():
            raise ValueError("fail")

        result = await fn()
        assert result is None


class TestMakeDefaultConditionReturnTrue:
    """Covers the inner 'return True' in _make_default_condition when giveup returns
    a non-bool non-float truthy value (_helpers.py:51)."""

    def test_giveup_with_truthy_string_via_functional_api(self):
        calls = []

        def fn():
            calls.append(1)
            raise ValueError("fail")

        with pytest.raises(ValueError):
            backon.retry(
                fn,
                backon.constant,
                exception=ValueError,
                giveup=lambda e: "yes",
                max_tries=3,
                jitter=None,
                interval=0,
                sleep=lambda s: None,
            )
        assert len(calls) == 3
