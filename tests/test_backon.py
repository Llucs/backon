import backon
from backon.types import Details


class TestImports:
    def test_on_predicate(self):
        assert hasattr(backon, "on_predicate")

    def test_on_exception(self):
        assert hasattr(backon, "on_exception")

    def test_wait_generators(self):
        assert hasattr(backon, "expo")
        assert hasattr(backon, "fibo")
        assert hasattr(backon, "constant")
        assert hasattr(backon, "runtime")
        assert hasattr(backon, "decay")

    def test_jitter(self):
        assert hasattr(backon, "full_jitter")
        assert hasattr(backon, "random_jitter")

    def test_version(self):
        assert backon.__version__ == "3.0.0"

    def test_details_importable(self):
        assert Details is not None

    def test_all_exports(self):
        expected = {
            "on_predicate",
            "on_exception",
            "retry",
            "Retrying",
            "constant",
            "expo",
            "decay",
            "fibo",
            "runtime",
            "full_jitter",
            "random_jitter",
            "disable",
            "enable",
        }
        assert set(backon.__all__) == expected
