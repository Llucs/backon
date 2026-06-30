from __future__ import annotations

import contextlib
from collections.abc import Callable, Generator
from typing import Any

from backon._common import (
    disable as _global_disable,
)
from backon._common import (
    enable as _global_enable,
)
from backon._common import (
    is_enabled,
)

TEST_CONFIG: dict[str, Any] = {
    "enabled": True,
    "max_retries": None,
    "backoff_multiplier": 1.0,
    "max_backoff": None,
}


@contextlib.contextmanager
def test_config(
    *,
    enabled: bool | None = None,
    max_retries: int | None = None,
    backoff_multiplier: float | None = None,
    max_backoff: float | None = None,
) -> Generator[None, None, None]:
    old = TEST_CONFIG.copy()
    if enabled is not None:
        TEST_CONFIG["enabled"] = enabled
    if max_retries is not None:
        TEST_CONFIG["max_retries"] = max_retries
    if backoff_multiplier is not None:
        TEST_CONFIG["backoff_multiplier"] = backoff_multiplier
    if max_backoff is not None:
        TEST_CONFIG["max_backoff"] = max_backoff
    try:
        yield
    finally:
        TEST_CONFIG.clear()
        TEST_CONFIG.update(old)


@contextlib.contextmanager
def disable_retries() -> Generator[None, None, None]:
    _global_disable()
    try:
        yield
    finally:
        _global_enable()


@contextlib.contextmanager
def enable_retries() -> Generator[None, None, None]:
    was_enabled = is_enabled()
    _global_enable()
    try:
        yield
    finally:
        if not was_enabled:
            _global_disable()


@contextlib.contextmanager
def limit_retries(n: int) -> Generator[None, None, None]:
    old = TEST_CONFIG["max_retries"]
    TEST_CONFIG["max_retries"] = n
    try:
        yield
    finally:
        TEST_CONFIG["max_retries"] = old


@contextlib.contextmanager
def remove_backoff() -> Generator[None, None, None]:
    old = TEST_CONFIG["backoff_multiplier"]
    TEST_CONFIG["backoff_multiplier"] = 0.0
    try:
        yield
    finally:
        TEST_CONFIG["backoff_multiplier"] = old


class RetryAssertionError(AssertionError):
    pass


def assert_retried(fn: Callable[[], Any], expected_tries: int) -> None:
    call_count = 0

    def wrapper() -> Any:
        nonlocal call_count
        call_count += 1
        return fn()

    try:
        wrapper()
    except BaseException:
        pass

    if call_count != expected_tries:
        raise RetryAssertionError(
            f"Expected {expected_tries} tries, got {call_count}"
        )


def assert_not_retried(fn: Callable[[], Any]) -> None:
    assert_retried(fn, 1)
