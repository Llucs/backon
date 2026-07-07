import warnings

warnings.warn(
    "backon._async is deprecated and will be removed in a future version. "
    "All retry logic is now handled by backon._retry, backon.on_exception, "
    "and backon.on_predicate.",
    DeprecationWarning,
    stacklevel=2,
)


def retry_predicate(*args, **kwargs):
    raise RuntimeError(
        "backon._async.retry_predicate is deprecated. "
        "Use backon.on_predicate or backon.retry instead."
    )


def retry_exception(*args, **kwargs):
    raise RuntimeError(
        "backon._async.retry_exception is deprecated. "
        "Use backon.on_exception or backon.retry instead."
    )
