import logging
from collections.abc import Callable, Coroutine, Generator, Sequence
from typing import Any, TypedDict, TypeVar, Union


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


T = TypeVar("T")

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])
_Handler = (
    Callable[["Details"], None] | Callable[["Details"], Coroutine[Any, Any, None]]
)
_Jitterer = Callable[[float], float]
_MaybeCallable = Union[T, Callable[[], T]]  # noqa: UP007
_MaybeLogger = str | logging.Logger | None
_MaybeSequence = Union[T, Sequence[T]]  # noqa: UP007
_Predicate = Callable[[T], bool]
_WaitGenerator = Callable[..., Generator[float, None, None]]

public_types = [
    "Details",
    "Details",
    "Handler",
    "Jitterer",
    "WaitGenerator",
    "Predicate",
]
