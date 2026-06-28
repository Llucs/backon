# backon

> Function decoration for backoff and retry — modern, fast, zero dependencies.

[![CI](https://github.com/Llucs/backon/actions/workflows/ci.yml/badge.svg)](https://github.com/Llucs/backon/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Llucs/backon/actions/workflows/codeql.yml/badge.svg)](https://github.com/Llucs/backon/actions/workflows/codeql.yml)
[![PyPI](https://img.shields.io/pypi/v/backon.svg)](https://pypi.org/project/backon/)
[![Python](https://img.shields.io/pypi/pyversions/backon.svg)](https://pypi.org/project/backon/)
[![License](https://img.shields.io/pypi/l/backon.svg)](https://github.com/Llucs/backon/blob/main/LICENSE)

backon is a modern evolution of [backoff](https://github.com/litl/backoff) — a zero-dependency Python library for retry with exponential backoff. It provides decorator, functional, and context manager APIs for both sync and async code.

---

## Features

- **Zero dependencies** — pure Python, stdlib only
- **Three APIs** — decorator (`@on_exception`, `@on_predicate`), functional (`retry()`), context manager (`Retrying`)
- **Async native** — same API works for `async def` functions
- **Full type hints** — validated with mypy, strict mode compatible
- **Global toggle** — `backon.disable()` / `backon.enable()` for testing
- **Custom sleep** — inject your own sleep function (useful for testing with `asyncio.Event`)
- **Multiple wait strategies** — exponential, constant, Fibonacci, decay, runtime, and composable chains
- **Jitter** — full jitter, random jitter, or none
- **Rich callbacks** — `on_attempt`, `on_backoff`, `on_success`, `on_giveup`, `before_sleep`
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

Parameters:

| Argument | Type | Default | Description |
|---|---|---|---|
| `wait_gen` | `WaitGenerator` | — | Wait strategy (expo, constant, fibo, etc.) |
| `exception` | `type` or `tuple[type]` | — | Exception class(es) to retry on |
| `max_tries` | `int` | `None` | Maximum number of attempts |
| `max_time` | `float` | `None` | Maximum total elapsed time |
| `jitter` | `Jitterer` or `None` | `full_jitter` | Jitter function |
| `giveup` | `Callable[[Exception], bool]` | `lambda e: False` | Stop retrying for matching exceptions |
| `on_success` | `Handler` | `None` | Called after successful attempt |
| `on_backoff` | `Handler` | `None` | Called before each retry |
| `on_giveup` | `Handler` | `None` | Called when retries exhausted |
| `on_attempt` | `Handler` | `None` | Called before each attempt |
| `before_sleep` | `Handler` | `None` | Called before sleeping |
| `logger` | `str` or `Logger` | `"backon"` | Logger name or instance |
| `raise_on_giveup` | `bool` | `True` | Raise final exception when giving up |
| `sleep` | `Callable[[float], Any]` | `None` | Custom sleep function |

#### `@backon.on_predicate(wait_gen, predicate, ...)`

Retry while the predicate matches the return value.

```python
@backon.on_predicate(backon.constant, predicate=lambda x: x is None, max_tries=5)
def poll():
    ...
```

### Functional API

#### `backon.retry(target, wait_gen, ...)`

```python
result = backon.retry(
    target=my_function,
    wait_gen=backon.expo,
    exception=ValueError,
    max_tries=3,
    jitter=backon.full_jitter,
)
```

Accepts all the same parameters as the decorators, plus `wait_gen_kwargs` as extra keyword arguments (e.g. `interval=0.5` for `constant`).

### Context Manager

#### `backon.Retrying(wait_gen, ...)`

```python
with backon.Retrying(backon.expo, exception=ValueError, max_tries=3) as r:
    r.call(my_function)

async with backon.Retrying(backon.constant, exception=ValueError, max_tries=3, interval=0.5) as r:
    await r.async_call(my_async_function)
```

Methods:

| Method | Description |
|---|---|
| `call(target, *args, **kwargs)` | Execute synchronously |
| `async_call(target, *args, **kwargs)` | Execute asynchronously |

---

## Wait Generators

| Generator | Signature | Description |
|---|---|---|
| `expo` | `(base=2, factor=1, max_value=None)` | Exponential backoff: `factor * base^n` |
| `constant` | `(interval=1)` | Fixed interval; accepts `float` or `Sequence[float]` |
| `fibo` | `(max_value=None)` | Fibonacci sequence |
| `runtime` | `(value=Callable)` | Dynamic wait from return value or exception |
| `decay` | `(initial_value=1, decay_factor=1, min_value=None)` | Exponential decay |
| `wait_random_exponential` | `(multiplier=1, max_value=None, exp_base=2, min_value=0)` | Randomized exponential |
| `wait_incrementing` | `(start=1, increment=1, max_value=None)` | Linear increment |

---

## Jitter

```python
@backon.on_exception(backon.expo, ValueError, jitter=backon.full_jitter)
def f():
    ...
```

| Jitter | Effect |
|---|---|
| `backon.full_jitter` | Random value between 0 and the wait time |
| `backon.random_jitter` | Random value within ±25% of the wait time |
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
| `wait` | `on_backoff` |

---

## Global Toggle

Useful in tests to disable retry logic:

```python
backon.disable()   # skip retry, call function directly
backon.enable()    # re-enable retry
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
| Functional API | Not supported | `retry()` function |
| Global toggle | Not supported | `disable()` / `enable()` |
| Custom sleep | Not supported | `sleep=` parameter |
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
pdm run pytest tests/
```

---

## License

[MIT](https://github.com/Llucs/backon/blob/main/LICENSE)
