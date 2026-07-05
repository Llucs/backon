from __future__ import annotations

import functools
import logging
import threading
import time as time_module
from typing import Any

_logger = logging.getLogger("backon")
_logger.addHandler(logging.NullHandler())

_GLOBAL_ENABLED = True

_TEST_CONFIG: dict[str, Any] = {
    "max_retries": None,
    "backoff_multiplier": 1.0,
    "max_backoff": None,
}


def disable():
    global _GLOBAL_ENABLED
    _GLOBAL_ENABLED = False


def enable():
    global _GLOBAL_ENABLED
    _GLOBAL_ENABLED = True


def is_enabled():
    return _GLOBAL_ENABLED


def _maybe_call(f, *args, **kwargs):
    if callable(f):
        try:
            return f(*args, **kwargs)
        except TypeError:
            return f
    else:
        return f


def _init_wait_gen(wait_gen, wait_gen_kwargs):
    kwargs = {k: _maybe_call(v) for k, v in wait_gen_kwargs.items()}
    initialized = wait_gen(**kwargs)
    initialized.send(None)
    return initialized


def _next_wait(wait, send_value, jitter, elapsed, max_time):
    value = wait.send(send_value)
    if jitter is not None:
        seconds = jitter(value)
    else:
        seconds = value

    seconds *= _TEST_CONFIG["backoff_multiplier"]

    if max_time is not None:
        seconds = min(seconds, max_time - elapsed)

    return seconds


def _apply_test_overrides(max_tries=None, max_time=None):
    tc = _TEST_CONFIG
    if tc["max_retries"] is not None:
        max_tries = tc["max_retries"]
    return max_tries, max_time


def _prepare_logger(logger):
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    return logger


def _config_handlers(
    user_handlers, *, default_handler=None, logger=None, log_level=None
):
    if isinstance(user_handlers, list) and logger is None:
        return user_handlers
    handlers = []
    if logger is not None:
        assert log_level is not None
        log_handler = functools.partial(
            default_handler, logger=logger, log_level=log_level
        )
        handlers.append(log_handler)

    if user_handlers is None:
        return handlers

    if hasattr(user_handlers, "__iter__"):
        handlers += list(user_handlers)
    else:
        handlers.append(user_handlers)

    return handlers


def _log_backoff(details, logger, log_level):
    msg = "Backing off %s(...) for %.1fs (%s)"
    exc = details.get("exception")
    if exc is not None:
        exc_fmt = f"{type(exc).__name__}: {exc}"
    else:
        exc_fmt = details.get("value", "unknown")
    log_args = [details["target"].__name__, details["wait"], exc_fmt]
    logger.log(log_level, msg, *log_args)


def _log_giveup(details, logger, log_level):
    msg = "Giving up %s(...) after %d tries (%s)"
    exc = details.get("exception")
    if exc is not None:
        exc_fmt = f"{type(exc).__name__}: {exc}"
    else:
        exc_fmt = details.get("value", "unknown")
    log_args = [details["target"].__name__, details["tries"], exc_fmt]
    logger.log(log_level, msg, *log_args)


def _now():
    return time_module.monotonic()


def _elapsed(start):
    return _now() - start


def _is_custom_wait(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_hot_loop_data: dict[str, float | int] = {"last_retry": 0.0, "count": 0}
_hot_loop_lock = threading.Lock()


def _check_hot_loop() -> None:
    now = time_module.monotonic()
    with _hot_loop_lock:
        prev = _hot_loop_data["last_retry"]
        if prev > 0 and now - prev < 0.1:
            _hot_loop_data["count"] += 1
        else:
            _hot_loop_data["count"] = 0
        _hot_loop_data["last_retry"] = now
        if _hot_loop_data["count"] >= 5:
            logging.getLogger("backon").warning(
                "Hot loop detected: %d retries in quick succession. "
                "Add jitter or increase backoff.",
                _hot_loop_data["count"],
            )
            _hot_loop_data["count"] = 0
