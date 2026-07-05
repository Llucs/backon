# backon Project Rules

## Versioning

- Update `version` in `pyproject.toml` on every change — this is the single source of truth.
- `__version__` in `backon/__init__.py` is read dynamically from `importlib.metadata`.
- Follow [SemVer](https://semver.org/): bump major for breaking changes, minor for features, patch for fixes.

## Before Every Commit

1. Run `ruff check backon/ tests/` — zero warnings allowed.
2. Run `mypy backon/` — zero errors allowed.
3. Run `pytest tests/ -q` — all tests must pass.
4. If you added a feature, you must add tests for it.
5. If you fixed a bug, add a test that would have caught it.
6. **Verify README is up to date**: every symbol in `__all__` must be documented, every parameter table must reflect the actual signatures, and every claim must be backed by the code.

## Code Style

- Target Python 3.10+. Use modern syntax: `|` for unions, `TypeVar` bounds, etc.
- Type hints on every function signature — no `Any` unless unavoidable.
- Zero comments in code. Code must be self-documenting.
- No docstrings unless the API is public and non-obvious.
- Follow the existing code patterns in the project.
- Line length: 88 characters.
- Use ruff with default rules (E, F, W, I).

## README

- `README.md` is the single source of truth for users. Every feature exported in `__all__` must be documented in the README.
- After adding a new feature, wait generator, condition, parameter, or public symbol:
  1. Add it to the appropriate README section (API Reference, Wait Generators, Conditions, etc.).
  2. If it needs a code example, add one.
  3. Run `python3 -c "import backon; assert '<your_feature>' in dir(backon)"` to confirm it's exported.
  4. Verify the README badge is still accurate (e.g., coverage percentage).
- The README must use the Standard README format, be truthful, and have every claim backed by the codebase.
- When removing or changing a feature, remove/update the corresponding README documentation immediately.

## Architecture

- Zero external dependencies. The stdlib is all you get.
- `_sync.py` — synchronous retry logic
- `_async.py` — async retry logic
- `_decorator.py` — decorator API (`on_exception`, `on_predicate`)
- `_retry.py` — functional API (`retry()`, `Retrying`)
- `_common.py` — shared helpers, global disable/enable
- `_wait_gen.py` — wait generators (`expo`, `constant`, `fibo`, etc.)
- `_jitter.py` — jitter functions
- `_typing.py` — internal type aliases
- `types.py` — public types (`Details`)
- Tests mirror the source structure in `tests/`.

## API Design

- Keep every function backoff had. Never remove, only add.
- New features must make backon **easier to use** than tenacity.
- The details dict passed to handlers must include `target`, `args`, `kwargs`, `tries`, `elapsed`, and relevant extras (`value`, `exception`, `wait`).
- Decorators must handle both sync and async functions transparently.
- Support `staticmethod` wrapping (order: `@decorator @staticmethod`).
- Export everything public in `__all__` in `__init__.py`.

## Testing

- Every test must be fast (< 100ms per test). Use `jitter=None` and small intervals.
- Cover: sync, async, exceptions, predicates, jitter, handlers, all wait generators.
- Cover edge cases: 0 max_tries, max_time expiry, giveup callbacks, global disable/enable.
- Use pytest with `asyncio_mode = auto` for async tests.
- Test that backoff issues are fixed (see issue list).

## Release Process

1. Bump `__version__` in `backon/__init__.py` and `version` in `pyproject.toml`.
2. Update `CHANGELOG.md` with the new version, date, and changes.
3. Commit with message `Release vX.Y.Z`.
4. Push to `main`.
5. Create a **GitHub Release** from the tag vX.Y.Z (click "Releases" → "Draft a new release").
6. The `Release` workflow auto-publishes to PyPI via trusted publishing (OIDC).
7. Verify at https://pypi.org/project/backon/.
