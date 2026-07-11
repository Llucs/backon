import contextlib

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


class TestPreconfiguredKwargsPreserved:
    def test_combine_preserves_subgenerator_kwargs(self):
        w = wait_combine(backon.constant(interval=0.1), backon.constant(interval=0.2))
        g = w()
        assert g.next() == 0.30000000000000004
        assert g.next() == 0.30000000000000004

    def test_plus_preserves_subgenerator_kwargs(self):
        w = backon.expo(base=3) + backon.constant(interval=0.5)
        g = w()
        assert g.next() == 1.5
        assert g.next() == 3.5
        assert g.next() == 9.5

    def test_chain_preserves_subgenerator_kwargs(self):
        w = backon.wait_chain(
            backon.constant(interval=0.1), backon.constant(interval=0.2)
        )
        g = w()
        assert g.next() == 0.1
        assert g.next() == 0.2
        assert g.next() == 0.1
        assert g.next() == 0.2

    def test_combine_in_decorator_uses_preconfigured(self):
        waits = []

        @backon.on_exception(
            wait_combine(backon.constant(interval=0.1), backon.constant(interval=0.2)),
            ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
            sleep=lambda s: waits.append(s),
        )
        def f():
            raise ValueError()

        with contextlib.suppress(ValueError):
            f()
        assert waits == [0.30000000000000004, 0.30000000000000004]

    def test_plus_in_decorator_uses_preconfigured(self):
        waits = []

        @backon.on_exception(
            backon.expo(base=3) + backon.constant(interval=0.5),
            ValueError,
            max_tries=3,
            jitter=None,
            logger=None,
            sleep=lambda s: waits.append(s),
        )
        def f():
            raise ValueError()

        with contextlib.suppress(ValueError):
            f()
        assert waits == [1.5, 3.5]

    def test_chain_in_decorator_uses_preconfigured(self):
        waits = []

        @backon.on_exception(
            backon.wait_chain(
                backon.constant(interval=0.1), backon.constant(interval=0.2)
            ),
            ValueError,
            max_tries=4,
            jitter=None,
            logger=None,
            sleep=lambda s: waits.append(s),
        )
        def f():
            raise ValueError()

        with contextlib.suppress(ValueError):
            f()
        assert waits == [0.1, 0.2, 0.1]

    def test_call_kwargs_override_preconfigured(self):
        w = backon.expo(base=3)
        g = w(base=5)
        assert g.next() == 1
        assert g.next() == 5
