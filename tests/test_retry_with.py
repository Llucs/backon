import pytest

import backon


class TestRetryWith:
    def test_retry_with_overrides_max_tries(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=5, jitter=None)
        def f():
            calls.append(1)
            raise ValueError("fail")

        wrapped = f.retry_with(max_tries=2)
        with pytest.raises(ValueError):
            wrapped()
        assert len(calls) == 2

    def test_retry_with_original_unaffected(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def f():
            calls.append(1)
            raise ValueError("fail")

        f.retry_with(max_tries=1)
        with pytest.raises(ValueError):
            f()
        assert len(calls) == 3

    def test_retry_with_chaining(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=5, jitter=None)
        def f():
            calls.append(1)
            raise ValueError("fail")

        wrapped = f.retry_with(max_tries=3).retry_with(max_tries=1)
        with pytest.raises(ValueError):
            wrapped()
        assert len(calls) == 1

    def test_retry_with_jitter_override(self):
        calls = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=3,
            jitter=backon.full_jitter,
        )
        def f():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        wrapped = f.retry_with(jitter=None)
        assert wrapped() == "ok"
        assert len(calls) == 2

    def test_retry_with_on_predicate(self):
        calls = []

        @backon.on_predicate(backon.constant, max_tries=5, interval=0, jitter=None)
        def f():
            calls.append(1)
            return None

        wrapped = f.retry_with(max_tries=2)
        result = wrapped()
        assert result is None
        assert len(calls) == 2

    def test_retry_with_name_reapplies(self):
        @backon.on_exception(backon.expo, ValueError, max_tries=1, jitter=None)
        def f():
            raise ValueError("fail")

        wrapped = f.retry_with()
        with pytest.raises(ValueError):
            wrapped()

    @pytest.mark.asyncio
    async def test_retry_with_async(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        async def f():
            calls.append(1)
            raise ValueError("fail")

        wrapped = f.retry_with(max_tries=2)
        with pytest.raises(ValueError):
            await wrapped()
        assert len(calls) == 2

    def test_retry_with_preserves_original_target_name(self):
        @backon.on_exception(backon.expo, ValueError, max_tries=1, jitter=None)
        def my_func():
            raise ValueError("fail")

        wrapped = my_func.retry_with(max_tries=1)
        assert wrapped.__name__ == "my_func"

    def test_retry_with_overrides_sleep(self):
        calls = []
        slept = []

        @backon.on_exception(backon.expo, ValueError, max_tries=2, jitter=None)
        def f():
            calls.append(1)
            raise ValueError("fail")

        wrapped = f.retry_with(sleep=lambda s: slept.append(s))
        with pytest.raises(ValueError):
            wrapped()
        assert len(calls) == 2
        assert len(slept) == 1
