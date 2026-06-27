from backon._typing import (
    _Handler,
    _Jitterer,
    _MaybeCallable,
    _MaybeLogger,
    _MaybeSequence,
    _Predicate,
)


class TestTyping:
    def test_handler_type(self):
        def sync_handler(details):
            pass

        h: _Handler = sync_handler
        assert callable(h)

    def test_jitterer_type(self):
        def jitter(value: float) -> float:
            return value

        j: _Jitterer = jitter
        assert callable(j)

    def test_predicate_type(self):
        def pred(value: int) -> bool:
            return value > 0

        p: _Predicate[int] = pred
        assert callable(p)

    def test_maybe_callable_with_value(self):
        v: _MaybeCallable[int] = 42
        assert v == 42

    def test_maybe_callable_with_callable(self):
        def fn() -> int:
            return 42

        v: _MaybeCallable[int] = fn
        assert callable(v)

    def test_maybe_logger_string(self):
        log: _MaybeLogger = "my-logger"
        assert isinstance(log, str)

    def test_maybe_logger_none(self):
        log: _MaybeLogger = None
        assert log is None

    def test_maybe_sequence_single(self):
        s: _MaybeSequence[int] = 42
        assert s == 42

    def test_maybe_sequence_tuple(self):
        s: _MaybeSequence[int] = (1, 2, 3)
        assert s == (1, 2, 3)
