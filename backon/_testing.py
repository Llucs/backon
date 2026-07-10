from __future__ import annotations

import contextlib
from collections.abc import Callable, Generator
from typing import Any

from backon._common import (
    _TEST_CONFIG,
    is_enabled,
)
from backon._common import (
    disable as _global_disable,
)
from backon._common import (
    enable as _global_enable,
)


@contextlib.contextmanager
def test_config(
    *,
    max_retries: int | None = None,
    backoff_multiplier: float | None = None,
    max_backoff: float | None = None,
) -> Generator[None, None, None]:
    old = _TEST_CONFIG.copy()
    if max_retries is not None:
        _TEST_CONFIG["max_retries"] = max_retries
    if backoff_multiplier is not None:
        _TEST_CONFIG["backoff_multiplier"] = backoff_multiplier
    if max_backoff is not None:
        _TEST_CONFIG["max_backoff"] = max_backoff
    try:
        yield
    finally:
        _TEST_CONFIG.clear()
        _TEST_CONFIG.update(old)


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
    old = _TEST_CONFIG["max_retries"]
    _TEST_CONFIG["max_retries"] = n
    try:
        yield
    finally:
        _TEST_CONFIG["max_retries"] = old


@contextlib.contextmanager
def remove_backoff() -> Generator[None, None, None]:
    old = _TEST_CONFIG["backoff_multiplier"]
    _TEST_CONFIG["backoff_multiplier"] = 0.0
    try:
        yield
    finally:
        _TEST_CONFIG["backoff_multiplier"] = old


class RetryAssertionError(AssertionError):
    pass


def assert_retried(fn: Callable[[], Any], expected_tries: int) -> None:
    call_count = 0

    def spy() -> Any:
        nonlocal call_count
        call_count += 1
        return fn()

    from backon._decorator import on_exception
    from backon._wait_gen import wait_none

    decorated = on_exception(
        wait_none,
        Exception,
        max_tries=expected_tries,
        jitter=None,
        raise_on_giveup=False,
        sleep=lambda s: None,
        logger=None,
    )(spy)
    decorated()

    if call_count != expected_tries:
        raise RetryAssertionError(f"Expected {expected_tries} tries, got {call_count}")


def assert_not_retried(fn: Callable[[], Any]) -> None:
    call_count = 0

    def spy() -> Any:
        nonlocal call_count
        call_count += 1
        return fn()

    from backon._decorator import on_exception
    from backon._wait_gen import wait_none

    decorated = on_exception(
        wait_none,
        Exception,
        max_tries=1,
        jitter=None,
        raise_on_giveup=False,
        sleep=lambda s: None,
        logger=None,
    )(spy)
    decorated()

    if call_count != 1:
        raise RetryAssertionError(f"Expected 1 try, got {call_count}")
