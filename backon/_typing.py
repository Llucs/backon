from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Coroutine, Sequence
from typing import Any, TypedDict, TypeVar, Union

from backon._wait_gen import _Wait

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:

    class ParamSpec:  # type: ignore[no-redef]
        def __init__(self, name: str) -> None: ...


class _Details(TypedDict):
    target: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    tries: int
    elapsed: float


class Details(_Details, total=False):
    wait: float
    value: Any
    exception: Exception


P = ParamSpec("P")

T = TypeVar("T")

R = TypeVar("R")

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])
_Handler = Union[
    Callable[["Details"], None],
    Callable[["Details"], Coroutine[Any, Any, None]],
]
_Jitterer = Callable[[float], float]
_MaybeCallable = Union[T, Callable[[], T]]
_MaybeLogger = Union[str, logging.Logger, None]
_MaybeSequence = Union[T, Sequence[T]]
_Predicate = Callable[[T], bool]
_WaitGenerator = Callable[..., _Wait]

public_types = [
    "Details",
    "Details",
    "Handler",
    "Jitterer",
    "WaitGenerator",
    "Predicate",
]
