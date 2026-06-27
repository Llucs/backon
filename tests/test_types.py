from backon.types import Details


class TestTypes:
    def test_details_is_dict(self):
        d: Details = {
            "target": lambda: None,
            "args": (),
            "kwargs": {},
            "tries": 1,
            "elapsed": 0.5,
        }
        assert d["tries"] == 1
        assert d["elapsed"] == 0.5

    def test_details_with_optional(self):
        d: Details = {
            "target": lambda: None,
            "args": (),
            "kwargs": {},
            "tries": 1,
            "elapsed": 0.5,
            "wait": 1.0,
            "value": "some-value",
            "exception": ValueError("test"),
        }
        assert d["wait"] == 1.0
        assert d["value"] == "some-value"
        assert isinstance(d["exception"], ValueError)
