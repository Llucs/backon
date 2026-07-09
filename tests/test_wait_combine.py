import backon
from backon._wait_gen import wait_combine


class TestWaitCombine:
    def test_combine_two(self):
        w = wait_combine(backon.constant, backon.constant)
        g = w(interval=1)
        assert g.next() == 2
        assert g.next() == 2

    def test_combine_three(self):
        w = wait_combine(backon.constant, backon.constant, backon.constant)
        g = w(interval=1)
        assert g.next() == 3

    def test_combine_with_expo(self):
        w = wait_combine(backon.expo, backon.expo)
        g = w(base=2)
        assert g.next() == 2
        assert g.next() == 4

    def test_combine_single(self):
        w = wait_combine(backon.constant)
        g = w(interval=5)
        assert g.next() == 5

    def test_combine_with_decorator(self):
        calls = []

        @backon.on_exception(
            wait_combine(backon.constant, backon.constant),
            ValueError,
            max_tries=3,
            jitter=None,
            interval=0,
        )
        def f():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("fail")
            return "ok"

        assert f() == "ok"
        assert len(calls) == 3

    def test_combine_in_retry_functional(self):
        calls = []

        def f():
            calls.append(1)
            if len(calls) < 2:
                raise ValueError("fail")
            return "ok"

        result = backon.retry(
            f,
            wait_combine(backon.constant, backon.constant),
            exception=ValueError,
            max_tries=3,
            jitter=None,
            interval=0,
        )
        assert result == "ok"
        assert len(calls) == 2

