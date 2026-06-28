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

## 3.0.0 - 2026-06-27

- Fork backoff → backon
- Drop Python 3.7, 3.8, 3.9 (minimum 3.10)
- Use `time.monotonic()` instead of `datetime.datetime.now()` for elapsed time
- Replace Poetry with PDM (PEP 621 metadata)
- Add py.typed marker
- Modernize type hints (remove compat shims)
- Add GitHub Actions CI with matrix testing (3.10–3.14)
- Add pre-commit config with ruff
- Update PyPI publishing to use Trusted Publishing + attestations
