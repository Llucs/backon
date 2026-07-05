# Contributing to backon

Thanks for considering contributing to backon!

## Setup

```bash
git clone https://github.com/Llucs/backon.git
cd backon
pip install pdm
pdm install
```

## Development

### Before every commit

1. Run `ruff check backon/ tests/` — zero warnings allowed.
2. Run `mypy backon/` — zero errors allowed.
3. Run `pytest tests/ -q` — all tests must pass.
4. If you added a feature, add tests for it.
5. If you fixed a bug, add a test that would have caught it.

### Code style

- Target Python 3.10+. Use modern syntax: `|` for unions, `TypeVar` bounds.
- Type hints on every function signature — no `Any` unless unavoidable.
- Zero comments in code. Code must be self-documenting.
- No docstrings unless the API is public and non-obvious.
- Line length: 88 characters.
- Use ruff with default rules (E, F, W, I).

### Testing

- Every test must be fast (< 100ms per test). Use `jitter=None` and small intervals.
- Cover: sync, async, exceptions, predicates, jitter, handlers, all wait generators.
- Cover edge cases: 0 max_tries, max_time expiry, giveup callbacks, global disable/enable.
- Async tests use `pytest-asyncio` with `asyncio_mode = auto`.

### Architecture

Source layout:

| File | Purpose |
|------|---------|
| `backon/_sync.py` | Synchronous retry logic |
| `backon/_async.py` | Async retry logic |
| `backon/_decorator.py` | Decorator API (`on_exception`, `on_predicate`) |
| `backon/_retry.py` | Functional API (`retry()`, `Retrying`) |
| `backon/_common.py` | Shared helpers, global disable/enable |
| `backon/_wait_gen.py` | Wait generators (`expo`, `constant`, `fibo`, etc.) |
| `backon/_jitter.py` | Jitter functions |
| `backon/_typing.py` | Internal type aliases |
| `backon/types.py` | Public types (`Details`) |
| `tests/` | Tests mirror the source structure |

## API design rules

- Keep every function backoff had. Never remove, only add.
- New features must make backon easier to use than tenacity.
- The details dict passed to handlers must include `target`, `args`, `kwargs`, `tries`, `elapsed`, and relevant extras (`value`, `exception`, `wait`).
- Decorators must handle both sync and async functions transparently.
- Support `staticmethod` wrapping (order: `@decorator @staticmethod`).
- Export everything public in `__all__` in `__init__.py`.

## README

- `README.md` is the single source of truth for users. Every feature exported in `__all__` must be documented.
- After adding a new feature, wait generator, condition, or public symbol:
  1. Add it to the appropriate README section.
  2. If it needs a code example, add one.
  3. Run `python3 -c "import backon; assert '<your_feature>' in dir(backon)"` to confirm it's exported.
  4. Verify the README badge is still accurate (e.g., coverage percentage).

## Versioning

- Update `version` in `pyproject.toml` on every change.
- `__version__` in `backon/__init__.py` is read dynamically from `importlib.metadata`.
- Follow [SemVer](https://semver.org/): bump major for breaking changes, minor for features, patch for fixes.

## Release process

1. Bump `version` in `pyproject.toml`.
2. Update `CHANGELOG.md` with the new version, date, and changes.
3. Commit with message `Release vX.Y.Z`.
4. Push to `main`.
5. Create a **GitHub Release** from the tag.
6. The `Release` workflow auto-publishes to PyPI via trusted publishing (OIDC).
7. Verify at https://pypi.org/project/backon/.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
