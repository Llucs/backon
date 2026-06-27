import functools
import logging
import sys
import time as time_module
import traceback

_logger = logging.getLogger("backon")
_logger.addHandler(logging.NullHandler())

_GLOBAL_ENABLED = True


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

    if max_time is not None:
        seconds = min(seconds, max_time - elapsed)

    return seconds


def _prepare_logger(logger):
    if isinstance(logger, str):
        logger = logging.getLogger(logger)
    return logger


def _config_handlers(
    user_handlers, *, default_handler=None, logger=None, log_level=None
):
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
    log_args = [details["target"].__name__, details["wait"]]

    exc_typ, exc, _ = sys.exc_info()
    if exc is not None:
        exc_fmt = traceback.format_exception_only(exc_typ, exc)[-1]
        log_args.append(exc_fmt.rstrip("\n"))
    else:
        log_args.append(details["value"])
    logger.log(log_level, msg, *log_args)


def _log_giveup(details, logger, log_level):
    msg = "Giving up %s(...) after %d tries (%s)"
    log_args = [details["target"].__name__, details["tries"]]

    exc_typ, exc, _ = sys.exc_info()
    if exc is not None:
        exc_fmt = traceback.format_exception_only(exc_typ, exc)[-1]
        log_args.append(exc_fmt.rstrip("\n"))
    else:
        log_args.append(details["value"])

    logger.log(log_level, msg, *log_args)


def _now():
    return time_module.monotonic()


def _elapsed(start):
    return _now() - start
