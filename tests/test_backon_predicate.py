import backon


class TestOnPredicate:
    def test_retry_on_falsey(self):
        calls = []

        @backon.on_predicate(backon.constant, jitter=None, interval=0.01, max_tries=3)
        def f():
            calls.append(1)
            return None

        assert f() is None
        assert len(calls) == 3

    def test_success_on_truthy(self):
        calls = []

        @backon.on_predicate(backon.constant, jitter=None, interval=0.01, max_tries=3)
        def f():
            calls.append(1)
            return "ok"

        assert f() == "ok"
        assert len(calls) == 1

    def test_custom_predicate(self):
        calls = []

        @backon.on_predicate(
            backon.constant, lambda x: x < 3, jitter=None, interval=0.01, max_tries=5
        )
        def f():
            calls.append(1)
            return len(calls)

        assert f() == 3
        assert len(calls) == 3

    def test_predicate_handler(self):
        handler_calls = []

        def handler(details):
            handler_calls.append(details)

        @backon.on_predicate(
            backon.constant, jitter=None, interval=0.01, max_tries=3, on_backoff=handler
        )
        def f():
            return None

        f()
        assert len(handler_calls) == 2

    def test_on_success_predicate(self):
        handler_calls = []

        def handler(details):
            handler_calls.append(details)

        @backon.on_predicate(
            backon.constant, jitter=None, interval=0.01, max_tries=3, on_success=handler
        )
        def f():
            return "ok"

        f()
        assert len(handler_calls) == 1
        assert "value" in handler_calls[0]
        assert handler_calls[0]["value"] == "ok"

    def test_max_tries_predicate(self):
        @backon.on_predicate(backon.constant, jitter=None, interval=0.01, max_tries=1)
        def f():
            return None

        assert f() is None

    def test_max_time_predicate(self):
        @backon.on_predicate(backon.constant, jitter=None, interval=0.01, max_time=0.05)
        def f():
            return None

        assert f() is None
