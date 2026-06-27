import logging
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Sequence,
    Tuple,
    TypedDict,
    TypeVar,
    Union,
)


class _Details(TypedDict):
    target: Callable[..., Any]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    tries: int
    elapsed: float


class Details(_Details, total=False):
    wait: float
    value: Any
    exception: Exception


T = TypeVar("T")

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
_WaitGenerator = Callable[..., Generator[float, None, None]]

public_types = [
    "Details",
    "Details",
    "Handler",
    "Jitterer",
    "WaitGenerator",
    "Predicate",
]
