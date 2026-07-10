<p align="center">
  <img
    src="https://raw.githubusercontent.com/Llucs/backon/main/assets/circle_logo.svg"
    width="160"
    alt="backon logo"
  />
</p>

<h1 align="center">backon</h1>

<p align="center">
  Function decoration for backoff and retry — modern, fast, zero dependencies.
</p>

<p align="center">
  <a href="https://github.com/Llucs/backon/actions/workflows/ci.yml">
    <img src="https://github.com/Llucs/backon/actions/workflows/ci.yml/badge.svg" />
  </a>

  <a href="https://github.com/Llucs/backon/actions/workflows/codeql.yml">
    <img src="https://github.com/Llucs/backon/actions/workflows/codeql.yml/badge.svg" />
  </a>

  <a href="https://codecov.io/gh/Llucs/backon">
    <img src="https://codecov.io/gh/Llucs/backon/branch/main/graph/badge.svg" />
  </a>

  <a href="https://pypi.org/project/backon/">
    <img src="https://img.shields.io/pypi/v/backon.svg" />
  </a>

  <a href="https://pypi.org/project/backon/">
    <img src="https://img.shields.io/pypi/pyversions/backon.svg" />
  </a>

  <a href="https://github.com/Llucs/backon/blob/main/LICENSE">
    <img src="https://img.shields.io/pypi/l/backon.svg" />
  </a>

  <a href="https://pepy.tech/projects/backon">
    <img src="https://static.pepy.tech/personalized-badge/backon?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=GREEN&left_text=downloads" />
  </a>
</p>

backon is a modern evolution of [backoff](https://github.com/litl/backoff) — a zero-dependency Python library for retry with exponential backoff. It provides decorator, functional, and context manager APIs for both sync and async code.

![backon demo](https://raw.githubusercontent.com/Llucs/backon/main/assets/demo.gif)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
  - [Decorators](#decorators)
  - [Functional API](#functional-api)
  - [Context Manager](#context-manager)
  - [Callers](#callers)
- [Wait Generators](#wait-generators)
- [Stop Conditions](#stop-conditions)
- [Retry Conditions](#retry-conditions)
- [Jitter](#jitter)
- [Handlers](#handlers)
- [Global Toggle](#global-toggle)
- [Generator Support](#generator-support)
- [Async Support](#async-support)
- [Custom Sleep](#custom-sleep)
- [Advanced Features](#advanced-features)
  - [Circuit Breaker](#circuit-breaker)
  - [Hedging](#hedging)
  - [Metrics](#metrics)
  - [Testing Utilities](#testing-utilities)
  - [Trio Support](#trio-support)
  - [Retry Context Inspection](#retry-context-inspection)
  - [Dynamic Backoff](#dynamic-backoff)
  - [Hot Loop Detection](#hot-loop-detection)
  - [Retry Statistics](#retry-statistics)
  - [Operator Composition](#operator-composition)
  - [Iterator API](#iterator-api)
- [Migrating from backoff](#migrating-from-backoff)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Zero dependencies** — pure Python, stdlib only
- **Four APIs** — decorator (`@on_exception`, `@on_predicate`), functional (`retry()`), context manager (`Retrying`), callable (`RetryingCaller` / `AsyncRetryingCaller`)
- **Async native** — same API works for `async def` functions
- **Generator native** — sync and async generators are retried transparently
- **Full type hints** — validated with mypy, py.typed included
- **Global toggle** — `backon.disable()` / `backon.enable()` for testing
- **Custom sleep** — inject your own sleep function (useful for testing with `asyncio.Event`)
- **Multiple wait strategies** — exponential, constant, Fibonacci, decay, runtime, randomized, incremental, and composable chains
- **`wait_combine()`** — sum multiple wait strategies per retry step
- **`retry_with()`** — override retry parameters per-call on decorated functions
- **Jitter** — full jitter, random jitter, or none
- **Rich callbacks** — `on_attempt`, `on_backoff`, `on_success`, `on_giveup`, `before_sleep`, `before`, `after`
- **Circuit breaker** — CLOSED/OPEN/HALF_OPEN states with automatic recovery
- **Hedging** — concurrent retry requests, first-success-wins
- **Prometheus / OpenTelemetry / structlog metrics** — optional, zero hard dependencies
- **Testing module** — `disable_retries()`, `limit_retries()`, `remove_backoff()`, `assert_retried()`
- **Trio support** — retry with the trio async framework
- **Operator overloading** — compose stops with `|` / `&`, wait generators with `+`
- **Iterator API** — `for attempt in Retrying(...):`
- **Modern packaging** — PEP 621, PDM, py.typed

---

## Installation

```bash
pip install backon
```

Requires Python 3.10+.

---

## Quick Start

### Retry on exception

```python
import backon

@backon.on_exception(backon.expo, ValueError, max_tries=3)
def fetch_data():
    return api.call()
```

### Retry on predicate

```python
@backon.on_predicate(backon.constant, max_tries=5, interval=0.5)
def poll_status():
    return check_ready()
```

### Functional API

```python
result = backon.retry(
    fetch_data,
    backon.expo,
    exception=ValueError,
    max_tries=3,
)
```

### Context manager

```python
with backon.Retrying(backon.expo, exception=ValueError, max_tries=3) as r:
    result = r.call(fetch_data)
```

Async variant:

```python
async with backon.Retrying(backon.constant, exception=ValueError, max_tries=3, interval=0.5) as r:
    result = await r.async_call(fetch_data)
```

---

## API Reference

### Decorators

#### `@backon.on_exception(wait_gen, exception, ...)`

Retry when the decorated function raises one of the specified exceptions.

```python
@backon.on_exception(backon.expo, (ValueError, TimeoutError), max_tries=5)
def fetch():
    ...
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `wait_gen` | `WaitGenerator` | — | Wait strategy (expo, constant, fibo, etc.) |
| `exception` | `type` or `tuple[type]` | — | Exception class(es) to retry on |
| `max_tries` | `int` or `Callable[[], int]` | `None` | Maximum number of attempts |
| `max_time` | `float`, `timedelta`, or `Callable` | `None` | Maximum total elapsed time |
| `jitter` | `Jitterer` or `None` | `full_jitter` | Jitter function |
| `giveup` | `Callable[[Exception], bool or float]` | `lambda e: False` | Stop retrying for matching exceptions; return `float` to override wait |
| `on_success` | `Handler` or list | `None` | Called after successful attempt |
| `on_backoff` | `Handler` or list | `None` | Called before each retry |
| `on_giveup` | `Handler` or list | `None` | Called when retries exhausted |
| `on_attempt` | `Handler` or list | `None` | Called before each attempt |
| `before_sleep` | `Handler` or list | `None` | Called before sleeping |
| `before` | `Handler` or list | `None` | Called before each attempt (lower-level than on_attempt) |
| `after` | `Handler` or list | `None` | Called after each attempt (lower-level than on_success/on_giveup) |
| `retry_error_callback` | `Callable[[dict], Any]` | `None` | Called when retry gives up instead of raising |
| `raise_on_giveup` | `bool` | `True` | Raise final exception when giving up |
| `logger` | `str` or `Logger` | `"backon"` | Logger name or instance |
| `backoff_log_level` | `int` | `logging.INFO` | Log level for backoff messages |
| `giveup_log_level` | `int` | `logging.ERROR` | Log level for giveup messages |
| `sleep` | `Callable[[float], Any]` | `None` | Custom sleep function |
| `rate_limit` | `RateLimiter` or `None` | `None` | Rate limiter to throttle retry calls |
| `attempt_timeout` | `float` or `None` | `None` | Maximum time in seconds for a single attempt |
| `**wait_gen_kwargs` | varies | — | Extra kwargs passed to the wait generator (e.g. `base=3`, `interval=0.5`) |

#### `@backon.on_predicate(wait_gen, predicate, ...)`

Retry while the predicate matches the return value.

```python
@backon.on_predicate(backon.constant, predicate=lambda x: x is None, max_tries=5)
def poll():
    ...
```

Accepts all parameters from `on_exception` except `exception` and `giveup`. Adds:

| Argument | Type | Default | Description |
|---|---|---|---|
| `predicate` | `Callable[[Any], bool]` | `operator.not_` | Retry when this returns `True` for the return value |

#### `decorator.retry_with(**overrides)`

Every decorated function (sync, async, generator) exposes a `.retry_with()` method that returns a new decorated function with overridden parameters:

```python
@backon.on_exception(backon.expo, ValueError, max_tries=5)
def fetch():
    ...

# Override max_tries
wrapped = fetch.retry_with(max_tries=3)

# Override jitter
wrapped = fetch.retry_with(jitter=None)

# Override wait generator and sleep
wrapped = fetch.retry_with(wait_gen=backon.constant, interval=0.1, sleep=lambda s: None)
```

The original decorated function is unaffected.

### Functional API

#### `backon.retry(target, wait_gen, ...)`

```python
result = backon.retry(
    target=my_function,
    wait_gen=backon.expo,
    exception=ValueError,
    max_tries=3,
)
```

Accepts all parameters from `on_exception` plus `on_predicate` extras, plus:

| Argument | Type | Default | Description |
|---|---|---|---|
| `condition` | `RetryCondition` | `None` | Advanced retry condition object |
| `stop` | `Stop` | `None` | Advanced stop condition object |
| `name` | `str` | `""` | Identifier for the retry call |
| `**wait_gen_kwargs` | varies | — | Extra kwargs passed to the wait generator |

If `target` is a coroutine function, `retry()` returns a coroutine. Otherwise it returns the result synchronously.

### Context Manager

#### `backon.Retrying(wait_gen, ...)`

```python
with backon.Retrying(backon.expo, exception=ValueError, max_tries=3) as r:
    r.call(my_function)

async with backon.Retrying(backon.constant, exception=ValueError, max_tries=3, interval=0.5) as r:
    await r.async_call(my_async_function)
```

| Method | Description |
|---|---|
| `call(target, *args, **kwargs)` | Execute synchronously |
| `async_call(target, *args, **kwargs)` | Execute asynchronously |
| `copy()` | Return a modified copy of the Retrying instance |
| `statistics` | Property returning dict with `attempt_number`, `elapsed`, `idle_for`, `start_time` |
| `call_state` | Property returning the current `RetryCallState` |
| `enabled` | Property to enable/disable retry per-instance |

**Arguments:** Same as `retry()`, plus `enabled` (default `True`).

### Callers

#### `backon.RetryingCaller(wait_gen, ...)`

A callable object with pre-bound exception type via `.on()`. Accepts the same configuration options as `Retrying` (`giveup`, `predicate`, `condition`, `stop`, the `on_*` handlers, `retry_error_callback`, `raise_on_giveup`, `logger`, `before`/`after`, etc.), forwarding them to the underlying retry loop on every call.

```python
caller = backon.RetryingCaller(backon.expo, max_tries=3)
caller = caller.on(ValueError)

result = caller(my_function, arg1, arg2)
```

#### `backon.AsyncRetryingCaller(wait_gen, ...)`

Async variant of `RetryingCaller` — same configuration surface, async dispatch.

```python
caller = backon.AsyncRetryingCaller(backon.expo, max_tries=3).on(ValueError)
result = await caller(my_async_function, arg1, arg2)
```

| Method | Description |
|---|---|
| `.on(exception)` | Return a copy bound to the given exception type |
| `.copy()` | Return a modified copy |
| `.__call__(target, *args, **kwargs)` | Execute with retry |

---

## Wait Generators

All wait generators are callables that produce a sequence of wait times. Pass extra kwargs (e.g. `interval=0.5`, `base=3`) as `**wait_gen_kwargs` to decorators and functions.

| Generator | Signature | Description |
|---|---|---|
| `expo` | `(base=2, factor=1, max_value=None)` | Exponential backoff: `factor * base^n` |
| `constant` | `(interval=1)` | Fixed interval; accepts `float` or `Sequence[float]` for varied intervals |
| `fibo` | `(max_value=None)` | Fibonacci sequence: 1, 1, 2, 3, 5, 8, ... |
| `runtime` | `(value=Callable)` | Dynamic wait from return value or exception — useful for `Retry-After` headers |
| `decay` | `(initial_value=1, decay_factor=1, min_value=None)` | Exponential decay: `initial * e^(-t * decay_factor)` |
| `wait_random_exponential` | `(multiplier=1, max_value=None, exp_base=2, min_value=0)` | Randomized exponential (uniform random between 0 and the exponential value) |
| `wait_incrementing` | `(start=1, increment=1, max_value=None)` | Linear increment: `start + n * increment` |
| `wait_chain` | `(*generators)` | Sequentially play through multiple generators |
| `wait_combine` | `(*generators)` | Sum all generator wait values per step (unlike `+` which chains sequentially) |
| `wait_exception` | `(value=Callable)` | Dynamic wait based on the caught exception |
| `wait_random` | `(min=0, max=1)` | Uniform random wait between min and max |
| `wait_exponential_jitter` | `(initial=1, max=60, exp_base=2, jitter=1)` | Exponential backoff with added random jitter |
| `wait_none` | `()` | Always returns 0 (no wait) |

**Composition:** Combine wait generators with `+` (sequential chain) or `wait_combine` (sum per step):

```python
# Sequential: wait_chain(expo, constant)
wait_strategy = backon.expo(base=3) + backon.constant(interval=0.5)

# Sum per step: wait_combine(expo, constant) — same kwargs to all sub-generators
from backon import wait_combine

@backon.on_exception(wait_combine(backon.expo, backon.constant), ValueError, max_tries=3)
def fetch():
    ...
```

`wait_combine` calls all sub-generators with the same kwargs on each step and returns the sum — useful when you want combined behaviors on every retry rather than a sequence.

---

## Stop Conditions

Stop conditions determine when retry should cease. They can be composed with `|` (any) and `&` (all).

| Condition | Description |
|---|---|
| `stop_after_attempt(max_attempts)` | Stop after N attempts |
| `stop_after_delay(max_delay)` | Stop after total elapsed time exceeds `max_delay` seconds |
| `stop_before_delay(max_delay)` | Stop if the *next* wait would exceed `max_delay` |
| `stop_all(*stops)` | Stop when all sub-conditions are met |
| `stop_any(*stops)` | Stop when any sub-condition is met |
| `stop_never()` | Never stop (retry indefinitely) |
| `stop_when_event_set(event)` | Stop when a `threading.Event` is set |

```python
from backon import stop_after_attempt, stop_after_delay, stop_any

stop = stop_after_attempt(5) | stop_after_delay(30.0)
```

---

## Retry Conditions

Retry conditions determine *whether* a retry should happen. They can be composed with `|` and `&`.

| Condition | Description |
|---|---|
| `retry_if_exception_type(exc_types)` | Retry if exception is an instance of given type(s) — accepts a single type or a tuple of types |
| `retry_if_exception(predicate)` | Retry if the exception matches a custom predicate |
| `retry_if_exception_message(message, match=None)` | Retry if exception message contains a string (or matches regex with `match="re"`) |
| `retry_if_result(predicate)` | Retry if the return value matches a predicate |
| `retry_if_not_result(predicate)` | Retry if the return value does NOT match a predicate |
| `retry_all(*conditions)` | Retry only when all conditions pass |
| `retry_any(*conditions)` | Retry when any condition passes |
| `retry_always()` | Always retry |
| `retry_never()` | Never retry |
| `retry_if_exception_cause_type(exc_types)` | Retry if the exception's cause chain matches the given type(s) |
| `retry_if_not_exception_type(exc_types)` | Retry if exception is NOT an instance of the given type(s) |
| `retry_if_not_exception_message(match, regex=False)` | Retry if exception message does NOT contain the given string |
| `retry_unless_exception_type(exc_types)` | Alias for `retry_if_not_exception_type` |

```python
from backon import retry_if_exception_type, retry_if_exception_message, retry_all

condition = retry_all(
    retry_if_exception_type(HTTPError),
    retry_if_exception_message("429"),
)
```

---

## Jitter

```python
@backon.on_exception(backon.expo, ValueError, jitter=backon.full_jitter)
def f():
    ...
```

| Jitter | Effect |
|---|---|
| `backon.full_jitter` | Random value between 0 and the calculated wait time |
| `backon.random_jitter` | Adds `random()` to the calculated wait time (~+0.5s on average) |
| `None` | No jitter (deterministic waits) |

---

## Handlers

Handlers receive a `details` dict with contextual information:

```python
def handler(details):
    print(f"Attempt {details['tries']}, elapsed {details['elapsed']:.2f}s")

@backon.on_exception(
    backon.expo, ValueError, max_tries=3,
    on_attempt=handler,
    on_backoff=handler,
    on_success=handler,
    on_giveup=handler,
)
def f():
    ...
```

Available keys in `details`:

| Key | Available in |
|---|---|
| `target` | All |
| `args`, `kwargs` | All |
| `tries` | All |
| `elapsed` | All |
| `value` | `on_success`, `on_backoff`, `on_giveup` |
| `exception` | `on_backoff`, `on_giveup` |
| `wait` | `on_backoff`, `before_sleep` |

---

## Global Toggle

Useful in tests to disable retry logic globally:

```python
backon.disable()   # skip retry, call function directly
backon.enable()    # re-enable retry
```

Per-instance toggle via `Retrying.enabled`:

```python
r = backon.Retrying(backon.expo, exception=ValueError, max_tries=3)
r.enabled = False
result = r.call(fn)  # no retry
```

---

## Generator Support

Sync and async generator functions are retried transparently. On each retry, the generator is restarted from scratch.

```python
@backon.on_exception(backon.expo, ValueError, max_tries=3)
def gen():
    yield 1
    yield 2
    raise ValueError("fail")
    yield 3  # reached on retry

result = list(gen())  # [1, 2, 3]

@backon.on_exception(backon.expo, ValueError, max_tries=3)
async def agen():
    yield 1
    raise ValueError("fail")
    yield 2

result = [item async for item in agen()]  # [1, 2]
```

`retry_with()` works on generators too:

```python
wrapped = gen.retry_with(max_tries=5)
```

---

## Async Support

All three APIs work with async functions transparently:

```python
@backon.on_exception(backon.expo, ValueError, max_tries=3)
async def fetch():
    return await api.call()

result = await backon.retry(fetch, backon.expo, exception=ValueError, max_tries=3)

async with backon.Retrying(backon.expo, exception=ValueError, max_tries=3) as r:
    result = await r.async_call(fetch)
```

---

## Custom Sleep

Replace the default sleep for testing or special environments:

```python
@backon.on_exception(
    backon.expo, ValueError, max_tries=3,
    sleep=lambda s: print(f"waiting {s}s"),
)
def f():
    ...

# With asyncio.Event for testing
import asyncio

event = asyncio.Event()
@backon.on_exception(
    backon.expo, ValueError, max_tries=3,
    sleep=backon.sleep_using_event(event),
)
async def f():
    ...
```

---

## Advanced Features

### Rate Limiter

Throttle retry calls to avoid overwhelming a backend.

```python
from backon import RateLimiter

limiter = RateLimiter(max_calls=10, period=1.0)  # max 10 calls per second

@backon.on_exception(backon.expo, ValueError, max_tries=5, rate_limit=limiter)
def fetch():
    ...
```

`RateLimitError` is raised when the rate limit is exceeded outside of retry context.

### TryAgain

Raise `TryAgain` inside a retried function to force an immediate retry, bypassing any condition or stop logic:

```python
import backon
from backon import TryAgain

@backon.on_exception(backon.expo, ValueError, max_tries=3)
def fetch():
    try:
        return api.call()
    except TemporaryIssue:
        raise TryAgain()
```

### Circuit Breaker

Circuit breaker with three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery).

```python
from backon import CircuitBreaker, BreakerRetrying, CircuitOpenError

breaker = BreakerRetrying(
    backon.expo, max_tries=3,
    breaker=CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=1,
    ),
)

try:
    result = breaker.call(fetch)
except CircuitOpenError:
    print("Circuit is open, skipping request")
```

| `CircuitBreaker` parameter | Default | Description |
|---|---|---|
| `failure_threshold` | `5` | Consecutive failures before opening the circuit |
| `recovery_timeout` | `60.0` | Seconds before transitioning from OPEN to HALF_OPEN |
| `half_open_max_calls` | `1` | Allowed calls in HALF_OPEN state before fully closing |
| `name` | `""` | Identifier for the breaker |

### Hedging

Run multiple retry attempts concurrently and return the first success.

```python
from backon import hedge, HedgingRetrying, on_hedge

# Functional
result = hedge(fetch, backon.expo, max_hedge=3)

# Decorator
@on_hedge(backon.expo, max_hedge=3)
def fetch():
    ...

# Context manager
with HedgingRetrying(backon.expo, max_hedge=3) as h:
    result = h.call(fetch)
```

| Parameter | Default | Description |
|---|---|---|
| `max_hedge` | `3` | Number of concurrent hedged requests |
| `timeout` | `None` | Maximum time to wait for any hedge |
| `on_hedge` | `None` | Callback when a hedge request is sent |

### Metrics

Optional Prometheus, OpenTelemetry, and structlog metrics. Each requires its corresponding package to be installed.

```python
from backon import PrometheusMetrics, OTelMetrics, StructlogMetrics, set_metrics_collector

# Prometheus
set_metrics_collector(PrometheusMetrics())

# OpenTelemetry
set_metrics_collector(OTelMetrics(meter_name="myapp.backon"))

# Structlog (structured logging)
set_metrics_collector(StructlogMetrics())
```

Auto-detection runs at import time (first available: prometheus_client > structlog > no-op); the active collector is queryable via `backon.get_metrics_collector()`:

```python
import backon

print(backon.get_metrics_collector())
```

Metrics collected:
- `backon_retry_attempts_total` (attempts, labeled by target and exception type)
- `backon_retry_success_total` (successes)
- `backon_retry_failure_total` (failures)
- `backon_circuit_breaker_open_total` / `backon_circuit_breaker_close_total`
- `backon_hedge_requests_total`
- `backon.retry.attempt_duration` (histogram, OTel only)

### Testing Utilities

```python
from backon import (
    disable_retries, enable_retries,
    test_config, limit_retries, remove_backoff,
    assert_retried, assert_not_retried,
)

# Context manager that skips retry for a block
with disable_retries():
    result = fetch()

# Limit max retries in tests
with limit_retries(2):
    fetch()

# Remove backoff delay entirely
with remove_backoff():
    fetch()

# Assert the function was retried N times
assert_retried(fetch, expected_tries=3)
```

### Trio Support

Retry with the trio async framework. The trio helpers live in the `backon._trio` module: the `trio` package is an optional dependency, so the trio helpers are deliberately not part of the top-level `backon` namespace and must be imported explicitly.

```python
from backon._trio import retry_exception, retry_predicate

@retry_exception(backon.expo, ValueError, max_tries=3)
async def fetch():
    ...
```

Requires `trio` to be installed.

### Retry Context Inspection

Check if code is running inside a retry and get the current attempt number anywhere in the call stack:

```python
from backon import is_retrying, get_attempt_number

def log_attempt():
    if is_retrying():
        print(f"This is attempt #{get_attempt_number()}")

@backon.on_exception(backon.expo, ValueError, max_tries=3)
def fetch():
    log_attempt()
    return api.call()
```

Uses `contextvars` — thread-safe and async-safe.

### Dynamic Backoff

Override the wait time per attempt by returning a `float` from the `giveup` callback. Useful for respecting `Retry-After` headers.

```python
def respect_retry_after(exc: HTTPError) -> float:
    return exc.response.headers.get("Retry-After", 1.0)

@backon.on_exception(backon.expo, HTTPError, giveup=respect_retry_after)
def fetch():
    ...
```

### Hot Loop Detection

When 5 or more retries occur with less than 100ms between them, backon logs a warning. This helps detect misconfigured retry policies before they cause issues.

### Retry Statistics

```python
r = backon.Retrying(backon.expo, exception=ValueError, max_tries=3)
result = r.call(fetch)

print(r.statistics)
# {'start_time': ..., 'attempt_number': 2, 'idle_for': 1.5, 'elapsed': 2.3}

print(r.call_state)
# RetryCallState(fn=..., attempt_number=2, ...)
```

### Operator Composition

Compose stops, conditions, and wait generators using Python operators:

```python
# Stop when either condition is met
stop = stop_after_attempt(5) | stop_after_delay(30.0)

# Retry when both conditions pass
cond = retry_if_exception_type(TimeoutError) & retry_if_result(lambda x: x is None)

# Wait with combined strategy
wait = backon.expo(base=3) + backon.constant(interval=0.5)
```

### Iterator API

```python
for attempt in backon.Retrying(backon.expo, exception=ValueError, max_tries=3):
    with attempt:
        result = fetch()
    if not attempt.failed:
        break
```

---

## Migrating from backoff

backon is a near-drop-in replacement. Change your imports:

```diff
- import backoff
+ import backon

- @backoff.on_exception(backoff.expo, ValueError, max_tries=3)
+ @backon.on_exception(backon.expo, ValueError, max_tries=3)
```

Key differences:

| Area | backoff | backon |
|---|---|---|
| Python support | 3.7+ | 3.10+ |
| Type hints | Partial | Full |
| `on_attempt` callback | Not supported | Supported |
| Context manager | Not supported | `Retrying` class |
| Functional API | Not supported | `retry()` function, `RetryingCaller` |
| Global toggle | Not supported | `disable()` / `enable()` |
| Custom sleep | Not supported | `sleep=` parameter |
| Circuit breaker | Not supported | `CircuitBreaker` + `BreakerRetrying` |
| Hedging | Not supported | `hedge()` / `on_hedge()` |
| Metrics | Not supported | Prometheus / OTel |
| Wait generator composition | Not supported | `+` operator |
| Stop / RetryCondition composition | Not supported | `\|` / `&` operators |
| Trio | Not supported | `backon._trio` (deliberately private, optional dep) |
| Iterator API | Not supported | `for attempt in Retrying():` |
| Build system | Poetry | PDM (PEP 621) |

---

## Contributing

```bash
git clone https://github.com/Llucs/backon.git
cd backon
pip install pdm
pdm install
pdm run ruff check backon/ tests/
pdm run mypy backon/
pdm run pytest tests/ -q
```

---

## License

[MIT](https://github.com/Llucs/backon/blob/main/LICENSE)

Made by Llucs with ❤️
