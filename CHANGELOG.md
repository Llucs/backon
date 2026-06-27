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
