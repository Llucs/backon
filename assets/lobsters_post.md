Title: Backon 4.0: Modern Python Retry Library (Zero Deps, Circuit Breaker)

I've been working on backon, a modern evolution of the backoff library — zero-dependency retry for Python 3.10+ with async native support.

Key features:
- 4 APIs: decorator, functional, context manager, callable
- Async native — same decorator works on sync and async
- Circuit breaker w/ CLOSED/OPEN/HALF_OPEN + auto recovery
- Hedging (concurrent retry, first success wins)
- 11 wait strategies + 12 retry conditions, composable with | &
- Rate limiter, Prometheus/OTel/structlog metrics
- Generator retry (sync and async)
- Trio support
- Full type hints, ~98% test coverage, 500+ tests
- Drop-in from backoff

v4.0 just dropped with optimizations (lazy handlers, monotonic_ns, dead code removal).

https://github.com/Llucs/backon
https://pypi.org/project/backon/
