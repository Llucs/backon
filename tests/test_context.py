import pytest

import backon
from backon._context import _retry_context_manager, get_attempt_number, is_retrying

_KW = dict(jitter=None, interval=0.01)


class TestIsRetrying:
    def test_not_retrying_outside_context(self):
        assert is_retrying() is False

    def test_get_attempt_number_outside_context(self):
        assert get_attempt_number() is None

    def test_is_retrying_inside_context(self):
        with _retry_context_manager(1):
            assert is_retrying() is True

    def test_get_attempt_number_inside_context(self):
        with _retry_context_manager(5):
            assert get_attempt_number() == 5

    def test_context_restored_after_exit(self):
        with _retry_context_manager(1):
            assert is_retrying() is True
        assert is_retrying() is False

    def test_nested_context(self):
        with _retry_context_manager(1):
            assert get_attempt_number() == 1
            with _retry_context_manager(2):
                assert get_attempt_number() == 2
            assert get_attempt_number() == 1

    def test_is_retrying_during_decorator_sync(self):
        attempts = []

        @backon.on_exception(backon.constant, ValueError, max_tries=3, **_KW)
        def flaky():
            attempts.append((is_retrying(), get_attempt_number()))
            raise ValueError("fail")

        with pytest.raises(ValueError):
            flaky()
        assert any(retrying for retrying, _ in attempts)

    @pytest.mark.asyncio
    async def test_is_retrying_during_decorator_async(self):
        attempts = []

        @backon.on_exception(backon.constant, ValueError, max_tries=3, **_KW)
        async def flaky():
            attempts.append((is_retrying(), get_attempt_number()))
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await flaky()
        assert any(retrying for retrying, _ in attempts)

    def test_is_retrying_during_retry_function(self):
        attempts = []

        def flaky():
            attempts.append((is_retrying(), get_attempt_number()))
            raise ValueError("fail")

        with pytest.raises(ValueError):
            backon.retry(
                flaky,
                backon.constant,
                exception=ValueError,
                max_tries=2,
                **_KW,
            )
        assert any(retrying for retrying, _ in attempts)

    @pytest.mark.asyncio
    async def test_is_retrying_during_retry_async_function(self):
        attempts = []

        async def flaky():
            attempts.append((is_retrying(), get_attempt_number()))
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await backon.retry(
                flaky,
                backon.constant,
                exception=ValueError,
                max_tries=2,
                **_KW,
            )
        assert any(retrying for retrying, _ in attempts)

    def test_attempt_number_increments(self):
        attempts = []

        @backon.on_exception(backon.constant, ValueError, max_tries=3, **_KW)
        def flaky():
            attempts.append(get_attempt_number())
            raise ValueError("fail")

        with pytest.raises(ValueError):
            flaky()
        assert attempts == [1, 2, 3]
