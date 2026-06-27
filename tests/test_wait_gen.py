from backon._wait_gen import constant, expo, fibo, runtime


class TestWaitGen:
    def test_expo_initial_values(self):
        g = expo(base=2, factor=1)
        next(g)
        assert next(g) == 1
        assert next(g) == 2
        assert next(g) == 4

    def test_expo_max_value(self):
        g = expo(base=2, factor=1, max_value=5)
        next(g)
        assert next(g) == 1
        assert next(g) == 2
        assert next(g) == 4
        assert next(g) == 5
        assert next(g) == 5

    def test_expo_base_factor(self):
        g = expo(base=3, factor=2)
        next(g)
        assert next(g) == 2
        assert next(g) == 6
        assert next(g) == 18

    def test_expo_send_ignored(self):
        g = expo()
        next(g)
        v1 = g.send(None)
        v2 = g.send("ignored")
        assert v1 == 1
        assert v2 == 2

    def test_fibo(self):
        g = fibo()
        next(g)
        assert next(g) == 1
        assert next(g) == 1
        assert next(g) == 2
        assert next(g) == 3
        assert next(g) == 5

    def test_fibo_max_value(self):
        g = fibo(max_value=3)
        next(g)
        assert next(g) == 1
        assert next(g) == 1
        assert next(g) == 2
        assert next(g) == 3
        assert next(g) == 3

    def test_constant_single(self):
        g = constant(interval=5)
        next(g)
        assert next(g) == 5
        assert next(g) == 5

    def test_constant_default(self):
        g = constant()
        next(g)
        assert next(g) == 1
        assert next(g) == 1

    def test_constant_iterable(self):
        g = constant(interval=[1, 2, 3])
        next(g)
        assert next(g) == 1
        assert next(g) == 2
        assert next(g) == 3

    def test_runtime(self):
        g = runtime(value=lambda x: x * 2)
        next(g)
        result = g.send(5)
        assert result == 10

    def test_runtime_multiple(self):
        g = runtime(value=lambda x: x * 2)
        next(g)
        assert g.send(1) == 2
        assert g.send(3) == 6
        assert g.send(10) == 20
