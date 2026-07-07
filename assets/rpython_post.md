Title: Backon 4.0 — Modern Python Retry Library (Zero Deps, Circuit Breaker, Async Native)

I just released v4.0.0 of backon, a zero-dependency retry library for Python 3.10+.

Why another retry library?

- **Four APIs**: decorator (@on_exception, @on_predicate), functional (retry()), context manager (Retrying), callable (RetryingCaller)
- **Async native**: same decorator works on sync and async functions
- **Generator native**: sync/async generators are retried transparently
- **Circuit breaker**: CLOSED/OPEN/HALF_OPEN with auto-recovery
- **Hedging**: concurrent retry requests, first-success-wins
- **11 wait strategies**: exponential, constant, Fibonacci, decay, runtime (Retry-After header), random, etc.
- **12 retry conditions** + operator composition (| &)
- **Composable**: stop_with = stop_after_attempt(5) | stop_after_delay(30)
- **Rate limiter**: throttle calls per second
- **Prometheus / OTel / structlog metrics** (optional, zero hard deps)
- **Testing utilities**: disable_retries(), limit_retries(), assert_retried(), remove_backoff()
- **Global toggle**: backon.disable() / backon.enable()
- **Trio support**
- **Iterator API**: for attempt in Retrying(...)
- **Zero dependencies**: pure Python, stdlib only
- **Full type hints**: py.typed included
- **~98% test coverage**, 500+ tests

v4.0.0 optimizations:
- Dead code removal (_sync.py / _async.py → DeprecationWarning stubs)
- Lazy log handlers (only created when first backoff/giveup fires)
- monotonic_ns() for lower overhead time retrieval
- Hot loop detection (5+ retries in <100ms → warning)

Drop-in upgrade from backoff: just change `import backoff` to `import backon`.

https://github.com/Llucs/backon

Feedback welcome!
