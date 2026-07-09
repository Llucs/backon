from backon._wait_gen import constant, expo, fibo, runtime


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

