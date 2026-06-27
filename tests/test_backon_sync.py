import pytest

import backon


class TestOnException:
    def test_success(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3)
        def f():
            calls.append(1)
            return "ok"

        assert f() == "ok"
        assert len(calls) == 1

    def test_retry_then_success(self):
        calls = []

        @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
        def f():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("retry")
            return "ok"

        assert f() == "ok"
        assert len(calls) == 3

    def test_giveup_after_max_tries(self):
        calls = []

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, raise_on_giveup=True
        )
        def f():
            calls.append(1)
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            f()
        assert len(calls) == 3

    def test_raise_on_giveup_false(self):
        calls = []

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, raise_on_giveup=False
        )
        def f():
            calls.append(1)
            raise ValueError("always fail")

        assert f() is None
        assert len(calls) == 3

    def test_giveup_condition(self):
        calls = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=5,
            jitter=None,
            giveup=lambda e: "fatal" in str(e),
        )
        def f():
            calls.append(1)
            raise ValueError("fatal error")

        with pytest.raises(ValueError):
            f()
        assert len(calls) == 1

    def test_on_backoff_handler(self):
        handler_calls = []

        def handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_backoff=handler
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()

        assert len(handler_calls) == 2

    def test_on_success_handler(self):
        handler_calls = []

        def handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_success=handler
        )
        def f():
            return "ok"

        f()
        assert len(handler_calls) == 1
        assert handler_calls[0]["tries"] == 1
        assert callable(handler_calls[0]["target"])
        assert handler_calls[0]["tries"] == 1

    def test_on_giveup_handler(self):
        handler_calls = []

        def handler(details):
            handler_calls.append(details)

        @backon.on_exception(
            backon.expo, ValueError, max_tries=3, jitter=None, on_giveup=handler
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
        assert len(handler_calls) == 1

    def test_multiple_handlers(self):
        handler_calls = []

        def h1(d):
            handler_calls.append("h1")

        def h2(d):
            handler_calls.append("h2")

        @backon.on_exception(
            backon.expo, ValueError, max_tries=2, jitter=None, on_backoff=[h1, h2]
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
        assert handler_calls == ["h1", "h2"]

    def test_exception_in_details(self):
        captured = []

        def handler(details):
            captured.append(details["exception"])

        @backon.on_exception(
            backon.expo, ValueError, max_tries=2, jitter=None, on_backoff=handler
        )
        def f():
            raise ValueError("test-exc")

        with pytest.raises(ValueError):
            f()
        assert isinstance(captured[0], ValueError)
        assert "test-exc" in str(captured[0])

    def test_logger_name(self):
        import logging

        logger = logging.getLogger("test-backon")
        logger.addHandler(logging.NullHandler())

        @backon.on_exception(
            backon.expo, ValueError, max_tries=2, jitter=None, logger="test-backon"
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()

    def test_logger_object(self):
        import logging

        logger = logging.getLogger("test-backon-obj")
        logger.addHandler(logging.NullHandler())

        @backon.on_exception(
            backon.expo, ValueError, max_tries=2, jitter=None, logger=logger
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()

    def test_staticmethod_wrapped(self):
        calls = []

        class MyClass:
            @backon.on_exception(backon.expo, ValueError, max_tries=3, jitter=None)
            @staticmethod
            def flaky():
                calls.append(1)
                raise ValueError("fail")

        with pytest.raises(ValueError):
            MyClass.flaky()
        assert len(calls) == 3

    def test_logger_none(self):
        @backon.on_exception(
            backon.expo, ValueError, max_tries=2, jitter=None, logger=None
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()

    def test_max_time_sync(self):
        @backon.on_exception(
            backon.expo, ValueError, max_time=0.1, jitter=None, raise_on_giveup=True
        )
        def f():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            f()
