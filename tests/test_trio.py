import pytest

from backon._trio import retry_exception, retry_predicate


try:
    import trio  # noqa: F401

    _trio_available = True
except ImportError:
    _trio_available = False


class TestTrioNotInstalled:
    def test_retry_predicate_raises_without_trio(self):
        if _trio_available:
            pytest.skip("trio is installed")

        def target():
            return None

        with pytest.raises(RuntimeError, match="trio is not installed"):
            retry_predicate(
                target,
                None,
                None,
                max_tries=3,
                max_time=None,
                jitter=None,
                on_success=[],
                on_backoff=[],
                on_giveup=[],
                on_attempt=[],
                sleep=lambda s: None,
                wait_gen_kwargs={},
            )

    def test_retry_exception_raises_without_trio(self):
        if _trio_available:
            pytest.skip("trio is installed")

        def target():
            raise ValueError("fail")

        with pytest.raises(RuntimeError, match="trio is not installed"):
            retry_exception(
                target,
                None,
                ValueError,
                max_tries=3,
                max_time=None,
                jitter=None,
                giveup=lambda e: False,
                on_success=[],
                on_backoff=[],
                on_giveup=[],
                on_attempt=[],
                raise_on_giveup=True,
                sleep=lambda s: None,
                wait_gen_kwargs={},
            )


class TestTrioImports:
    def test_trio_flag(self):
        from backon._trio import _trio_available as ta

        assert ta is _trio_available

    def test_module_importable(self):
        import backon._trio as t

        assert hasattr(t, "retry_predicate")
        assert hasattr(t, "retry_exception")
        assert hasattr(t, "_trio_available")
        assert t._trio_available == _trio_available
