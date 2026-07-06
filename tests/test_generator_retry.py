import pytest

import backon


class TestGeneratorRetry:
    def test_sync_generator_retries_on_exception(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def gen():
            calls.append(1)
            yield 1
            yield 2
            if len(calls) < 2:
                raise ValueError("fail")
            yield 3

        result = list(gen())
        assert result == [1, 2, 3]
        assert len(calls) == 2

    def test_sync_generator_giveup(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=2, jitter=None)
        def gen():
            calls.append(1)
            yield 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            list(gen())
        assert len(calls) == 2

    def test_sync_generator_retries_on_predicate(self):
        calls = []

        @backon.on_predicate(
            backon.constant,
            max_tries=3,
            interval=0,
            jitter=None,
            predicate=lambda x: len(x) == 0,
        )
        def gen():
            calls.append(1)
            if len(calls) < 2:
                return
            yield 1
            yield 2

        result = list(gen())
        assert result == [1, 2]
        assert len(calls) == 2

    def test_sync_generator_disabled(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def gen():
            calls.append(1)
            yield 1
            raise ValueError("fail")

        backon.disable()
        try:
            with pytest.raises(ValueError):
                list(gen())
            assert len(calls) == 1
        finally:
            backon.enable()

    def test_sync_generator_no_retry_on_success(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def gen():
            calls.append(1)
            yield 1
            yield 2

        result = list(gen())
        assert result == [1, 2]
        assert len(calls) == 1

    def test_sync_generator_retry_with(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=5, jitter=None)
        def gen():
            calls.append(1)
            yield 1
            raise ValueError("fail")

        wrapped = gen.retry_with(max_tries=3)
        with pytest.raises(ValueError):
            list(wrapped())
        assert len(calls) == 3

    def test_sync_generator_empty(self):
        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def gen():
            yield from []

        result = list(gen())
        assert result == []

    @pytest.mark.asyncio
    async def test_async_generator_retries_on_exception(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        async def gen():
            calls.append(1)
            yield 1
            yield 2
            if len(calls) < 2:
                raise ValueError("fail")
            yield 3

        result = []
        async for item in gen():
            result.append(item)
        assert result == [1, 2, 3]
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_async_generator_giveup(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=2, jitter=None)
        async def gen():
            calls.append(1)
            yield 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            async for _item in gen():
                pass
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_async_generator_no_retry_on_success(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        async def gen():
            calls.append(1)
            yield 1
            yield 2

        result = []
        async for item in gen():
            result.append(item)
        assert result == [1, 2]
        assert len(calls) == 1
