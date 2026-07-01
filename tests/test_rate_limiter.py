import backon
from backon import RateLimiter, RateLimitError


class TestRateLimiter:
    def test_acquire_returns_bool(self):
        rl = RateLimiter(max_calls=3, period=1.0)
        assert rl.acquire() is True
        assert rl.acquire() is True
        assert rl.acquire() is True
        assert rl.acquire() is False

    def test_unlimited_with_period_zero(self):
        rl = RateLimiter(max_calls=5, period=0.0)
        for _ in range(100):
            assert rl.acquire() is True

    def test_rate_limit_error_is_exception(self):
        assert issubclass(RateLimitError, Exception)

    def test_call_wrapper_raises_on_limit(self):
        rl = RateLimiter(max_calls=1, period=1.0)
        result = rl(lambda: 42)
        assert result == 42
        try:
            rl(lambda: 0)
            raise AssertionError("expected RateLimitError")
        except RateLimitError:
            pass

    def test_wait_time(self):
        rl = RateLimiter(max_calls=1, period=1.0)
        assert rl.wait_time() == 0.0
        rl.acquire()
        wt = rl.wait_time()
        assert 0.0 < wt <= 1.0

    def test_with_on_exception_decorator(self):
        rl = RateLimiter(max_calls=100, period=1.0)
        calls = []

        @backon.on_exception(
            backon.expo,
            ValueError,
            max_tries=3,
            jitter=None,
            rate_limit=rl,
        )
        def f():
            calls.append(1)
            return "ok"

        result = f()
        assert result == "ok"
        assert len(calls) == 1

    def test_with_retry_functional(self):
        rl = RateLimiter(max_calls=100, period=1.0)
        calls = []

        def f():
            calls.append(1)
            return "ok"

        result = backon.retry(
            f,
            backon.expo,
            max_tries=3,
            jitter=None,
            rate_limit=rl,
        )
        assert result == "ok"
        assert len(calls) == 1

    def test_rate_limiter_with_retry_on_exception(self):
        rl = RateLimiter(max_calls=100, period=1.0)

        @backon.on_exception(
            backon.expo,
            RuntimeError,
            max_tries=3,
            jitter=None,
            rate_limit=rl,
        )
        def fail_twice():
            fail_twice.calls += 1
            if fail_twice.calls < 3:
                raise RuntimeError("fail")
            return "success"

        fail_twice.calls = 0

        result = fail_twice()
        assert result == "success"
        assert fail_twice.calls == 3
