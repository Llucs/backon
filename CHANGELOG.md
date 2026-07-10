## 4.2.3 - 2026-07-10

- Documentation: rewrite the `AGENTS.md` `Architecture` section to match the actual repository layout (#24). The previous text pointed AI agents and contributors to `backon/_sync.py`, `backon/_async.py`, and a non-existent `backon/_retry.py` for retry logic; those are now deprecation stubs / non-existent files. The new section documents the `_retry/` subpackage (`_api.py`, `_classes.py`, `_decide.py`, `_fast.py`, `_helpers.py`, `_inner.py`, `_loops.py`) alongside `_circuit_breaker.py`, `_conditions.py`, `_context.py`, `_hedging.py`, `_instrumentation.py`, `_rate_limiter.py`, `_state.py`, `_testing.py`, `_trio.py`, and the `py.typed` PEP 561 marker, and explicitly calls out `_sync.py` / `_async.py` as `DeprecationWarning` stubs. Notes that `tests/` uses feature-oriented naming rather than a one-`test_`-per-source mirror.

## 4.2.2 - 2026-07-10

- Fix `stop_before_delay(max_delay)` actually stopping the retry loop (#23). `_decide_outcome` now writes the upcoming wait into `state.outcome.wait` before invoking the `Stop` predicate, so `elapsed + wait >= max_delay` evaluates against the real upcoming wait rather than `0`. Verified with a wait-incrementing loop where `stop_before_delay(0.3)` stops at the 3rd attempt (sum of sleeps < 0.31s). The README description is updated to: "Stop if the upcoming wait would make `elapsed + wait >= max_delay`".
- Documentation (#23): the README "Context manager" section now clarifies that `Retrying.__exit__`/`__aexit__` (and the `BreakerRetrying`/`HedgingRetrying` twins) are a scoping device and do not re-raise the final exception — use `r.statistics` after the call. The Rate Limiter section now clarifies that `RateLimitError` is raised only by direct `RateLimiter` usage; inside a retry loop exceeding the limit just throttles by sleeping. The migration section adds a note that `backon.__version__` is read from `importlib.metadata` (a `pip install backon` is required; running from a source checkout without installing returns `"0.0.0"`).
- The contextvars claim ("thread-safe and async-safe") is now backed by every retry configuration (the fast-path fix landed in #19 / 4.1.4 already covers it), and the operator-composition example is now backed by code (the kwarg-preservation fix landed in #15 / 4.1.5).
- Add `test_stop_before_delay_actually_stops_retry_loop` and `test_stop_before_delay_predicate_based_actually_stops` (`tests/test_edge_cases.py`) covering the exception-based and predicate-based retry paths.

## 4.2.1 - 2026-07-10

- Documentation: replace private-module imports in README examples with the public API (#21). The Circuit Breaker, Hedging, Metrics, Testing Utilities, and auto-detection snippets now use `from backon import ...` for symbols already in `__all__`. The `_auto_detect_collector` private helper was replaced with `backon.get_metrics_collector()`. The Trio section and migration table now explicitly document `backon._trio` as the deliberately private, optional-dependency surface (trio helpers are intentionally not re-exported).

## 4.2.0 - 2026-07-10

- `RetryingCaller` and `AsyncRetryingCaller` now accept and forward the full set of retry options (#20). Previously they silently dropped `giveup`, `predicate`, `condition`, `stop`, the `on_*` handlers, `retry_error_callback`, `raise_on_giveup`, `logger`, `before`/`after`, and `name`. The Dynamic Backoff feature (giveup predicate / float return) and the Handlers API are now reachable through the callable caller surface, consistent with `Retrying`, `retry()`, and the decorators.
- Add `TestCallerForwardsFullOptions` (12 tests) to `tests/test_retrying_caller.py` covering giveup, predicate-based retry, on_attempt / on_giveup handlers, condition / stop composition objects, retry_error_callback, raise_on_giveup, copy preservation, and the async twins.

## 4.1.5 - 2026-07-10

- Fix `assert_retried()` / `assert_not_retried()` ignoring their `fn` argument (#22). Both helpers now wrap the user-supplied `fn` in a counting spy, drive it through `on_exception`, and assert the spy was invoked exactly `expected_tries` (resp. exactly 1) times. `assert_retried` failing when `fn` does not actually raise is now detectable instead of silently passing.
- Add `tests/test_assertions.py` (7 tests) covering fn invocation, the non-raising-fn failure path, non-`ValueError` exceptions, and the raising-fn path of `assert_not_retried`.
- Fix wait generators losing pre-configured kwargs when composed with `+`, `wait_combine()`, or `wait_chain()` (#15). `_Wait` now stores its original constructor args/kwargs and `__call__` merges them with any caller-supplied kwargs, so pre-configured instances such as `backon.expo(base=3)` and `backon.constant(interval=0.2)` preserve their configuration through composition and re-instantiation inside the retry loop.
- Add `TestPreconfiguredKwargsPreserved` (7 tests) to `tests/test_wait_combine.py` covering `wait_combine`, the `+` operator, `wait_chain`, decorator integration, and call-time kwarg override.

## 4.1.4 - 2026-07-10

- Fix `is_retrying()` / `get_attempt_number()` returning `None` inside a retry when the fast path was active (#19). The fast paths `_retry_fast_sync` and `_retry_fast_async` now enter `_retry_context_manager(state.tries)` around the `target()` call, matching the non-fast path. The README's "contextvars — thread-safe and async-safe" guarantee now holds for every retry configuration, not only those that force the slow path.
- Add `TestFastPathRetryContext` (5 tests) to `tests/test_fast_path.py` covering sync, async, functional API, and the outside-retry default.

## 4.1.3 - 2026-07-10

- Fix `raise_on_giveup=False` being silently ignored in the fast path (#17): `_retry_fast_sync` and `_retry_fast_async` now thread the `raise_on_giveup` flag and return `None` on giveup when it is `False`, matching the non-fast path (`_retry_loop_*`).
- Fix the fast path raising `RuntimeError("stop triggered on success")` when the `stop` predicate fires on the same iteration where the target call succeeds but the condition still asks for a retry (#18): the fast path now returns the successful `ret` in that case, matching `_decide_outcome`/`_retry_loop_*` behaviour.
- Add `tests/test_fast_path.py` covering both regressions (sync + async, direct `_retry_fast_*` calls and via decorators).

## 4.1.2 - 2026-07-10

- Fix `hedge()` raising `TypeError: 'NoneType' object is not callable` whenever the target function raised (issue #16). The hedge helpers now build a default `RetryCondition` via `_make_default_condition(exception, giveup, predicate)` before fanning out, mirroring `_retry_sync`/`_retry_async`. Hedge futures also honour the final exception by passing `raise_on_giveup=True` so that a fully-failed hedge surfaces the real error instead of `None`.
- Add `tests/test_hedging.py` with sync/async/decorator/context-manager coverage for `hedge()`, `on_hedge()`, and `HedgingRetrying` (18 tests, 1 skipped pending #18).

## 4.1.1 - 2026-07-09

- Fix mypy type errors and ruff formatting issues in 4.1.0 release.

## 4.1.0 - 2026-07-09

- Add fast path (`_fast.py`) — monolithic inline retry loop for the common case (no handlers, no state tracking). Avoids `RetryState`/`Attempt` dataclass allocations, `_decide_outcome()`, `_call_hdlrs`, `_retry_context_manager`, and `to_details()` dict creation. ~3μs per success call (was ~22μs).
- Replace generator-based wait generators with class-based `_Wait` subclasses — removes `.send()`/`yield` overhead, uses direct `.next(send_value)` method. ~15% faster wait gen iteration.
- Add `_is_fast_path()` gate — decorator, functional, and callable APIs auto-detect when fast path is safe and dispatch to the monolithic loop.
- Remove dead generator functions `_wait_random_exponential` and `_wait_chain` (replaced by class-based `_WaitRandomExponential` and `_WaitChain`).
- Performance (benchmarked against tenacity): 1.2x faster on success path (42µs vs 51µs), 3.6x faster on 3-retry path (107µs vs 387µs).

## 4.0.0 - 2026-07-07

- Remove dead code (`_sync.py`, `_async.py`) — 507 lines of duplicate logic no longer imported anywhere; replaced with `DeprecationWarning` stubs
- Make `_config_handlers` lazy — default log handlers are no longer created eagerly at decoration time; uses `_LazyLogHandler` to defer `functools.partial` creation until first backoff/giveup event
- Replace `time.monotonic()` with `time.monotonic_ns()` in `_now()` and `_check_hot_loop()` for lower overhead time retrieval
- Remove `_sync.py` and `_async.py` from coverage omit — they now count toward coverage

## 3.8.0 - 2026-07-06

- Add `wait_combine()` — sum multiple wait strategies at each step (unlike `+` which chains sequentially)
- Add `retry_with()` on decorated functions — create modified copies at the call site (e.g. `fn.retry_with(max_tries=2)`)
- Add generator retry support — sync generators and async generators are now automatically retried, restarting from scratch on each attempt
- Add `StructlogMetrics` — structured logging via structlog, auto-detected when `structlog` is installed
- Add auto-detection of instrumentation — `prometheus_client` and `structlog` are detected automatically, no manual `set_metrics_collector()` needed for basic setups

## 3.7.3 - 2026-07-05

- Fix ruff formatting in `_decide.py`, `_loops.py`, `_testing.py`

## 3.7.2 - 2026-07-05

- Fix `_check_hot_loop` thread-safety — properly guarded with `threading.Lock`
- Fix line length violation in `_common.py` (89 → 88)

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
