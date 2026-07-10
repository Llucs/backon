import pytest

import backon


class TestAssertRetried:
    def test_invokes_user_fn(self):
        calls = []

        def my_fetch():
            calls.append("called")
            raise ValueError()

        backon.assert_retried(my_fetch, expected_tries=3)
        assert calls == ["called", "called", "called"]

    def test_non_raising_fn_fails(self):
        calls = []

        def my_fetch():
            calls.append("called")
            return "ok"

        with pytest.raises(backon.RetryAssertionError) as exc_info:
            backon.assert_retried(my_fetch, expected_tries=3)
        assert "Expected 3 tries" in str(exc_info.value)
        assert calls == ["called"]

    def test_expected_tries_in_message(self):
        with pytest.raises(backon.RetryAssertionError) as exc_info:
            backon.assert_retried(lambda: "ok", expected_tries=5)
        assert "got 1" in str(exc_info.value)

    def test_raises_non_value_error(self):
        calls = []

        def my_fetch():
            calls.append("called")
            raise KeyError()

        backon.assert_retried(my_fetch, expected_tries=2)
        assert len(calls) == 2


class TestAssertNotRetried:
    def test_invokes_user_fn_once(self):
        calls = []

        def my_fetch():
            calls.append("called")
            return "ok"

        backon.assert_not_retried(my_fetch)
        assert calls == ["called"]

    def test_invokes_raising_user_fn_once(self):
        calls = []

        def my_fetch():
            calls.append("called")
            raise ValueError()

        backon.assert_not_retried(my_fetch)
        assert calls == ["called"]


class TestRetryAssertionErrorIsAssertionError:
    def test_is_assertion_error(self):
        assert issubclass(backon.RetryAssertionError, AssertionError)
