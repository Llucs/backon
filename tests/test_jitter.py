from backon._jitter import full_jitter, random_jitter


class TestJitter:
    def test_full_jitter_range(self):
        for value in [0, 0.5, 1, 10, 100]:
            for _ in range(100):
                result = full_jitter(value)
                assert 0 <= result <= value

    def test_full_jitter_zero(self):
        result = full_jitter(0)
        assert result == 0

    def test_random_jitter_positive(self):
        for value in [0, 0.5, 1, 10]:
            for _ in range(100):
                result = random_jitter(value)
                assert result >= value

    def test_random_jitter_upper_bound(self):
        for value in [0, 0.5, 1]:
            for _ in range(100):
                result = random_jitter(value)
                assert result < value + 1

    def test_random_jitter_consistency(self):
        for value in [0, 0.5, 1]:
            result = random_jitter(value)
            assert isinstance(result, float)
