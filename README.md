# backon

> Function decoration for backoff and retry — modern, fast, and zero dependencies.

[![CI](https://github.com/Llucs/backon/actions/workflows/ci.yml/badge.svg)](https://github.com/Llucs/backon/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/backon.svg)](https://pypi.org/project/backon/)
[![Python](https://img.shields.io/pypi/pyversions/backon.svg)](https://pypi.org/project/backon/)
[![License](https://img.shields.io/pypi/l/backon.svg)](https://github.com/Llucs/backon/blob/main/LICENSE)

## Why backon?

**backon** is the evolution of [backoff](https://github.com/litl/backoff) — a zero-dependency Python library for retry with exponential backoff. If you know backoff, you already know backon.

| Feature | backoff | tenacity | backon |
|---|---|---|---|
| Python 3.10+ native | ❌ | ❌ | ✅ |
| Type hints | ❌ partial | ✅ | ✅ full |
| `disable()` / `enable()` toggle | ❌ | ❌ | ✅ |
| Context manager API | ❌ | ✅ | ✅ |
| Functional `retry()` API | ❌ | ✅ | ✅ |
| `on_attempt` callback | ❌ | ✅ | ✅ |
| Custom sleep injection | ❌ | ❌ | ✅ |
| `time.monotonic()` | ❌ | ✅ | ✅ |
| PDM / PEP 621 build | ❌ | ❌ | ✅ |
| Zero dependencies | ✅ | ✅ | ✅ |

## Quick Start

```bash
pip install backon
```

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
result = backon.retry(fetch_data, backon.expo, exception=ValueError, max_tries=3)
```

### Context manager

```python
with backon.Retrying(backon.expo, exception=ValueError, max_tries=3) as r:
    result = r.call(fetch_data)
```

## Wait Generators

| Generator | Description |
|---|---|
| `expo(base=2, factor=1, max_value=None)` | Exponential backoff |
| `constant(interval=1)` | Constant interval |
| `fibo(max_value=None)` | Fibonacci backoff |
| `runtime(value=callable)` | Dynamic wait from return value |
| `decay(initial_value=1, decay_factor=1, min_value=None)` | Exponential decay |

## Jitter

```python
@backon.on_exception(backon.expo, ValueError, jitter=backon.full_jitter)
```

- `full_jitter` — random between 0 and the wait value
- `random_jitter` — random ±25% around the wait value
- `None` — no jitter

## Handlers

```python
def log_attempt(details):
    print(f"Attempt {details['tries']} for {details['target'].__name__}")

@backon.on_exception(
    backon.expo, ValueError, max_tries=3,
    on_attempt=log_attempt,
    on_backoff=log_attempt,
    on_success=log_attempt,
    on_giveup=log_attempt,
)
def f():
    ...
```

Available `details` keys: `target`, `args`, `kwargs`, `tries`, `elapsed`, `value` (on_success/on_backoff/on_giveup), `exception` (on_backoff/on_giveup), `wait` (on_backoff).

## Global Toggle

```python
backon.disable()   # skip retry, call function directly
backon.enable()    # re-enable retry
```

## Async Support

Everything works with `async def` functions — no extra flags needed.

```python
@backon.on_exception(backon.expo, ValueError, max_tries=3)
async def fetch_data():
    return await api.call()
```

## Custom Sleep

```python
@backon.on_exception(backon.expo, ValueError, max_tries=3,
                     sleep=lambda s: print(f"waiting {s}s"))
def f():
    ...
```

## Installation

```bash
pip install backon
```

Requires Python 3.10+.

## Migrating from backoff

backon is a drop-in replacement for most backoff users. Just change:

```python
# before
import backoff
@backoff.on_exception(backoff.expo, ValueError, max_tries=3)

# after
import backon
@backon.on_exception(backon.expo, ValueError, max_tries=3)
```

## License

MIT
