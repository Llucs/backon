from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Generator
from typing import Any, cast

_retry_context: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("_retry_context", default=None)
)


@contextlib.contextmanager
def _retry_context_manager(attempt_number: int) -> Generator[None, None, None]:
    token = _retry_context.set({"attempt_number": attempt_number})
    try:
        yield
    finally:
        _retry_context.reset(token)


def is_retrying() -> bool:
    return _retry_context.get() is not None


def get_attempt_number() -> int | None:
    ctx = _retry_context.get()
    if ctx is None:
        return None
    return cast(int, ctx["attempt_number"])
