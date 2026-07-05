## 3.7.1 - 2026-07-05

- Fix `assert_retried()` — now properly drives retries through `_retry_sync_inner` instead of direct call
- Fix `test_config()` / `limit_retries()` / `remove_backoff()` — no longer no-ops; now modify `_common._TEST_CONFIG` which is read by all retry loops
- Fix `retry_unless_exception_type` — now inherits from `retry_if_not_exception_type`, removing duplicate code
- Remove coverage `omit` — all modules now count toward the 95% coverage threshold (actual: 98.23%)
- Fix Iterator API `Retrying.__iter__` — uses meaningful target name instead of `lambda: None`
- Fix `_hot_loop_data` thread-safety — guarded by `threading.Lock`
- Refactor `_retry_loop_sync`/`_async` — extract shared decision logic into `_decide_outcome`, reducing ~460 lines of duplicate logic to ~140
- Split `_retry.py` (1277 lines) into 7 focused submodules under `_retry/` package
- Cover 98.23% of codebase (+39 new tests across edge cases, thread-safety, circuit breaker, wait generators)

## 3.7.0 - 2026-07-01

- Add `RateLimiter` + `RateLimitError` — sliding window rate limiter integrated into all retry loops
- Add `attempt_timeout` parameter — per-attempt timeout via `ThreadPoolExecutor` (sync) or `asyncio.wait_for` (async)
- Export all hidden modules to public API: `CircuitBreaker`, `BreakerRetrying`, `hedge`, `on_hedge`, `HedgingRetrying`, `PrometheusMetrics`, `OTelMetrics`, `disable_retries`, `test_config`, `assert_retried`, `wait_random`, `wait_exponential_jitter`, `wait_none`, `Details`, `retry_if_not_exception_type`, `retry_unless_exception_type`, `retry_if_not_exception_message`, `retry_if_exception_cause_type`
- Fix `RetryingCaller` to raise `TypeError` for async targets (use `AsyncRetryingCaller` instead)
- Fix `AsyncRetryingCaller` to properly use `async def wrapped()` wrapper
- Fix `ThreadPoolExecutor` shutdown in attempt_timeout to use `wait=False` / cancel futures
- Wrap `wait_random`, `wait_exponential_jitter`, `wait_none` as `_Wait` objects for `+` composition
- Add docstrings to `TryAgain`, `RetryError`, `AttemptTimeoutError`, `sleep_using_event`
- Rewrite README.md in Standard README format covering all v3.7.0 features

## 3.6.1 - 2026-06-30

- Fix CI: coverage 88% → 91%, ruff formatting
- Refactor `_retry_loop_sync`/`_async` to use `_next_wait` (reduce duplication)
- Add tests for edge cases (default jitter, custom condition float, sequence exceptions, Retrying iterator)

## 3.6.0 - 2026-06-30

- Add `is_retrying()` / `get_attempt_number()` — `contextvars`-based retry context inspection
- Add dynamic backoff via `giveup` return value — return `float` to override wait per attempt (respect Retry-After headers)
- Add hot loop detection — warns when 5+ retries occur with < 100ms between them
- Add `RetryingCaller` / `AsyncRetryingCaller` — callable objects with pre-bound exception type via `.on()`
- Export new public API: `is_retrying`, `get_attempt_number`, `RetryingCaller`, `AsyncRetryingCaller`

## 3.5.0 - 2026-06-30

- Add `CircuitBreaker` + `BreakerRetrying` — circuit breaker pattern with CLOSED/OPEN/HALF_OPEN states
- Add `hedge()` / `on_hedge()` / `HedgingRetrying` — concurrent hedging requests (first-success-wins)
- Add `MetricsCollector`, `PrometheusMetrics`, `OTelMetrics` — optional Prometheus/OpenTelemetry instrumentation
- Add `testing` module — `disable_retries()`, `limit_retries()`, `remove_backoff()`, assertion helpers
- Add `_trio` module — retry support for trio async framework
- Modernize packaging: PEP 639 SPDX license, `license-files`
- CI: add concurrency cancel-in-progress, pip cache
- Release: separate build/publish jobs with PEP 740 attestations

## 3.4.0 - 2026-06-28

- Add `RetryCallState` dataclass with `elapsed`, `statistics`, `seconds_since_start`, `to_details()` for per-call introspection
- Add `before`/`after` hooks in `retry()`, `Retrying()`, `on_predicate()`, `on_exception()`
- Add `Retrying.call_state` property returning current `RetryCallState`
- Add `Retrying.statistics` property returning call state statistics (attempt_number, elapsed, idle_for, start_time)
- Wire `RetryCallState` through `_retry_loop_sync`/`_retry_loop_async` for future instrumentation
- Export `RetryCallState` from `backon` public API

## 3.3.0 - 2026-06-28

- Optimize performance: 7.6x faster than tenacity and backoff in retry benchmarks
- Replace expensive `traceback.format_exception_only()` with direct `str(exc)` formatting in log handlers
- Remove double handler configuration in decorator path (was calling handlers twice)
- Skip `time.sleep(0)` when wait time is zero
- Inline hot functions (`_elapsed`, `_now`, `_next_wait`) in retry loops
- Add `_retry_sync_inner`/`_retry_async_inner` fast path for pre-configured handlers
- Add `_config_handlers` fast path to skip `hasattr` for pre-configured lists
- Remove unused imports (`sys`, `traceback`, `_next_wait`)

## 3.2.0 - 2026-06-28

- Add `|` / `&` operator overloading for `Stop` and `RetryCondition` composition
- Add `+` operator for wait generator composition (e.g. `expo + constant`)
- Add iterator API: `for attempt in Retrying(...): with attempt: fn()`
- Add `Retrying.copy()` method for creating modified copies
- Add `name` parameter to `retry()` and `Retrying()` for identification
- Add `retry_if_not_exception_type`, `retry_unless_exception_type` conditions
- Add `retry_if_not_exception_message(match, regex)` condition
- Add `retry_if_exception_cause_type(exc_types)` condition (walks `__cause__` chain)
- Add `wait_random(min, max)` — uniform random wait generator
- Add `wait_exponential_jitter(initial, max, jitter)` — exponential backoff with jitter
- Add `wait_none()` — no-wait sentinel generator
- Add `_to_seconds()` helper with `timedelta` support for `max_time`
- Add `AttemptResult` dataclass for iterator API results
- Use `ParamSpec` for proper decorator type signature preservation
- Update AGENTS.md to reflect new versioning rules

## 3.1.0 - 2026-06-28

- Add functional API `retry()` — call `backon.retry(fn, backon.constant, max_tries=5, ...)`
- Add `Retrying` context manager — `with backon.Retrying(...) as r: r.call(fn)`
- Add `Retrying.async_call()` for async context managers
- Add `TryAgain` exception for manual retry signaling
- Add `RetryCondition` / `Stop` type hierarchy and helper constructors (`retry_if_exception_type`, `stop_after_attempt`, etc.)
- Fix `giveup` callback in `on_exception` decorator — exceptions matching `giveup` are now correctly re-raised
- Fix `wait_gen_kwargs` double-wrapping bug that broke extra kwargs (`interval`, `max_time`, etc.) in the functional API
- Add `backon.disable()` / `backon.enable()` global toggles
- Version now read dynamically from `importlib.metadata` (single source: `pyproject.toml`)

## 3.0.0 - 2026-06-28

- Fork backoff → backon
- Drop Python 3.7, 3.8, 3.9 (minimum 3.10)
- Use `time.monotonic()` instead of `datetime.datetime.now()` for elapsed time
- Replace Poetry with PDM (PEP 621 metadata)
- Add py.typed marker
- Modernize type hints (remove compat shims)
- Add GitHub Actions CI with matrix testing (3.10–3.14)
- Add pre-commit config with ruff
- Update PyPI publishing to use Trusted Publishing + attestations
