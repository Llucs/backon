import contextlib

import pytest
import trio

from backon._state import AttemptTimeoutError
from backon._trio import retry_exception, retry_predicate
from backon._wait_gen import constant


def _make_predicate_target(rl):
    async def target():
        rl.append(1)
        await trio.sleep(0.5)
        return "ok"
    return target


def _make_exception_target(rl):
    async def target():
        rl.append(1)
        await trio.sleep(0.5)
        raise ValueError("fail")
    return target


class TestTrioNotInstalled:
    def test_retry_predicate_raises_without_trio(self, monkeypatch):
        monkeypatch.setattr("backon._trio._trio_available", False)

        def target():
            return None

        with pytest.raises(RuntimeError, match="trio is not installed"):
            retry_predicate(
                target,
                None,
                None,
                max_tries=3,
                max_time=None,
                jitter=None,
                on_success=[],
                on_backoff=[],
                on_giveup=[],
                on_attempt=[],
                sleep=lambda s: None,
                wait_gen_kwargs={},
            )

    def test_retry_exception_raises_without_trio(self, monkeypatch):
        monkeypatch.setattr("backon._trio._trio_available", False)

        def target():
            raise ValueError("fail")

        with pytest.raises(RuntimeError, match="trio is not installed"):
            retry_exception(
                target,
                None,
                ValueError,
                max_tries=3,
                max_time=None,
                jitter=None,
                giveup=lambda e: False,
                on_success=[],
                on_backoff=[],
                on_giveup=[],
                on_attempt=[],
                raise_on_giveup=True,
                sleep=lambda s: None,
                wait_gen_kwargs={},
            )


class TestTrioImports:
    def test_trio_flag_true(self):
        from backon._trio import _trio_available

        assert _trio_available

    def test_trio_available_imports(self):
        import backon._trio as t

        assert hasattr(t, "retry_predicate")
        assert hasattr(t, "retry_exception")
        assert hasattr(t, "_trio_available")
        assert t._trio_available


class TestTrioAttemptTimeout:
    def test_predicate_timeout_triggers_retry(self):
        rl = []
        wrapped = retry_predicate(
            _make_predicate_target(rl),
            constant,
            lambda v: False,
            max_tries=3,
            max_time=None,
            jitter=None,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=0.01,
        )

        with contextlib.suppress(Exception):
            trio.run(wrapped)
        assert len(rl) == 3

    def test_exception_timeout_triggers_retry(self):
        rl = []
        wrapped = retry_exception(
            _make_exception_target(rl),
            constant,
            ValueError,
            max_tries=3,
            max_time=None,
            jitter=None,
            giveup=lambda e: False,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            raise_on_giveup=False,
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=0.01,
        )

        with contextlib.suppress(Exception):
            trio.run(wrapped)
        assert len(rl) == 3

    def test_predicate_timeout_giveup_after_exhaustion(self):
        rl = []
        wrapped = retry_predicate(
            _make_predicate_target(rl),
            constant,
            lambda v: False,
            max_tries=3,
            max_time=None,
            jitter=None,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=0.01,
        )

        trio.run(wrapped)
        assert len(rl) == 3

    def test_exception_timeout_giveup_after_exhaustion(self):
        rl = []
        wrapped = retry_exception(
            _make_exception_target(rl),
            constant,
            ValueError,
            max_tries=3,
            max_time=None,
            jitter=None,
            giveup=lambda e: False,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            raise_on_giveup=False,
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=0.01,
        )

        result = trio.run(wrapped)
        assert result is None
        assert len(rl) == 3

    def test_exception_timeout_raises_on_giveup(self):
        rl = []
        wrapped = retry_exception(
            _make_exception_target(rl),
            constant,
            ValueError,
            max_tries=3,
            max_time=None,
            jitter=None,
            giveup=lambda e: False,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            raise_on_giveup=True,
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=0.01,
        )

        with pytest.raises(AttemptTimeoutError):
            trio.run(wrapped)
        assert len(rl) == 3

    def test_no_timeout_predicate_succeeds(self):
        rl = []

        async def target():
            rl.append(1)
            return "ok"

        wrapped = retry_predicate(
            target,
            constant,
            lambda v: False,
            max_tries=3,
            max_time=None,
            jitter=None,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=999,
        )

        result = trio.run(wrapped)
        assert result == "ok"
        assert len(rl) == 1

    def test_no_timeout_exception_succeeds(self):
        rl = []

        async def target():
            rl.append(1)
            return "ok"

        wrapped = retry_exception(
            target,
            constant,
            Exception,
            max_tries=3,
            max_time=None,
            jitter=None,
            giveup=lambda e: False,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            raise_on_giveup=False,
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
            attempt_timeout=999,
        )

        result = trio.run(wrapped)
        assert result == "ok"
        assert len(rl) == 1

    def test_predicate_retry_without_timeout(self):
        rl = []

        async def target():
            rl.append(1)
            return "retry"

        wrapped = retry_predicate(
            target,
            constant,
            lambda v: v == "retry",
            max_tries=3,
            max_time=None,
            jitter=None,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
        )

        result = trio.run(wrapped)
        assert result == "retry"
        assert len(rl) == 3

    def test_exception_retry_without_timeout(self):
        rl = []

        async def target():
            rl.append(1)
            raise ValueError("fail")

        wrapped = retry_exception(
            target,
            constant,
            ValueError,
            max_tries=3,
            max_time=None,
            jitter=None,
            giveup=lambda e: False,
            on_success=[],
            on_backoff=[],
            on_giveup=[],
            on_attempt=[],
            raise_on_giveup=False,
            sleep=trio.sleep,
            wait_gen_kwargs={"interval": 0},
        )

        result = trio.run(wrapped)
        assert result is None
        assert len(rl) == 3
