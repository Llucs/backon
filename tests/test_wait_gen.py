from backon._wait_gen import (
    constant,
    expo,
    fibo,
    runtime,
    wait_incrementing,
    wait_random,
)


class TestWaitGen:
    def test_expo_initial_values(self):
        g = expo(base=2, factor=1)
        assert g.next() == 1
        assert g.next() == 2
        assert g.next() == 4

    def test_expo_max_value(self):
        g = expo(base=2, factor=1, max_value=5)
        assert g.next() == 1
        assert g.next() == 2
        assert g.next() == 4
        assert g.next() == 5
        assert g.next() == 5

    def test_expo_base_factor(self):
        g = expo(base=3, factor=2)
        assert g.next() == 2
        assert g.next() == 6
        assert g.next() == 18

    def test_expo_send_ignored(self):
        g = expo()
        v1 = g.next()
        v2 = g.next()
        assert v1 == 1
        assert v2 == 2

    def test_fibo(self):
        g = fibo()
        assert g.next() == 1
        assert g.next() == 1
        assert g.next() == 2
        assert g.next() == 3
        assert g.next() == 5

    def test_fibo_max_value(self):
        g = fibo(max_value=3)
        assert g.next() == 1
        assert g.next() == 1
        assert g.next() == 2
        assert g.next() == 3
        assert g.next() == 3

    def test_constant_single(self):
        g = constant(interval=5)
        assert g.next() == 5
        assert g.next() == 5

    def test_constant_default(self):
        g = constant()
        assert g.next() == 1
        assert g.next() == 1

    def test_constant_iterable(self):
        g = constant(interval=[1, 2, 3])
        assert g.next() == 1
        assert g.next() == 2
        assert g.next() == 3

    def test_runtime(self):
        g = runtime(value=lambda x: x * 2)
        result = g.next(5)
        assert result == 10

    def test_runtime_multiple(self):
        g = runtime(value=lambda x: x * 2)
        assert g.next(1) == 2
        assert g.next(3) == 6
        assert g.next(10) == 20


class TestPositionalArgs:
    def test_constant_positional(self):
        g = constant(0.05)
        assert g.next() == 0.05

    def test_expo_positional(self):
        g = expo(10)
        assert g.next() == 1

    def test_expo_positional_with_kwarg(self):
        g = expo(3, factor=2)
        assert g.next() == 2
        assert g.next() == 6

    def test_fibo_positional(self):
        g = fibo(100)
        assert g.next() == 1

    def test_wait_incrementing_positional(self):
        g = wait_incrementing(2)
        assert g.next() == 2

    def test_wait_random_positional(self):
        g = wait_random(0, 5)
        assert 0 <= g.next() <= 5

    def test_kwargs_still_work(self):
        g = expo(base=3, factor=2)
        assert g.next() == 2
        assert g.next() == 6

    def test_preconfigured_with_positional(self):
        w = expo(max_value=10)
        g = w(3)
        assert g.next() == 1
        assert g.next() == 3
        assert g.next() == 9
        assert g.next() == 10
