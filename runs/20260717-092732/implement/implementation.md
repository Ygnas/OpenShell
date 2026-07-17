# Implementation Summary

## Pull Request

**URL:** https://github.com/Ygnas/OpenShell/pull/12  
**Branch:** `feat/retry-with-backoff-http-helper`  
**Commit:** `d928551a`

---

## What Was Changed

### New files created

| File | Description |
|------|-------------|
| `python/openshell/utils/__init__.py` | Package initialiser making `utils` a proper Python sub-package |
| `python/openshell/utils/http_helpers.py` | The `retry_with_backoff` helper implementation |
| `python/openshell/utils/http_helpers_test.py` | Unit test suite (9 test cases) |

No existing files were modified.

---

## Files Modified

None — this change is purely additive.

---

## Approach Taken

### Module structure

A new `utils/` sub-package was created under `python/openshell/` to give the helper a clean, discoverable home without polluting the top-level `openshell` namespace.

### Implementation (`http_helpers.py`)

`retry_with_backoff` is a generic wrapper that accepts:

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `func` | `Callable[[], httpx.Response]` | — | Zero-argument callable that executes the HTTP request |
| `max_retries` | `int` | `3` | Number of retry attempts (not counting the initial call) |
| `base_delay` | `float` | `1.0` | Base delay in seconds for the backoff formula |

**Retry trigger conditions:**
- HTTP `429` (Too Many Requests)
- Any HTTP `5xx` status code (500–511)

**Backoff formula:**  
`wait = base_delay * 2^attempt + random.random()`  
where `attempt` is 0-indexed and `random.random()` adds jitter in the range `[0, 1)`.

**Control flow:**
1. Call `func()`. If it raises an exception (e.g. network error), propagate immediately — no retry for transport errors.
2. If the response status is not in the retryable set, return it immediately.
3. Otherwise, log a `WARNING` with the status code, attempt number, and computed wait time, then `time.sleep(wait)`.
4. After exhausting all `max_retries` attempts, raise a `RuntimeError` describing the last failed status code.

**Typing:**  
Uses a `TypeVar` bound to `httpx.Response` so the return type is preserved. `httpx` itself is imported only under `TYPE_CHECKING` to keep the module usable even if `httpx` is not installed at import time (it is a declared runtime dependency of the package, but this avoids circular-import concerns).

**Logging:**  
Uses a module-level `logging.Logger` (`__name__`), consistent with the project's use of standard-library logging throughout the Python SDK.

### Tests (`http_helpers_test.py`)

Nine `pytest`-style tests cover:

1. Immediate success on 200 — callable invoked exactly once, response returned.
2. Non-retryable 4xx (404) — not retried, response returned.
3. Retry-then-succeed for each retryable code (429, 500, 502, 503, 504).
4. Exhaustion raises `RuntimeError` with the status code (503 variant).
5. Exhaustion raises `RuntimeError` with the status code (429 variant).
6. Backoff timing — `time.sleep` receives the correct value (`base_delay * 2^0 + jitter`).
7. No `time.sleep` on immediate success.
8. Exception from `func` propagates immediately with no retries.
9. Default parameters — function works correctly with no keyword arguments.

`time.sleep` and `random.random` are patched in all timing-sensitive tests to keep the suite fast and deterministic.

### Code conventions followed

- SPDX license header (`Apache-2.0`) on every new file.
- `from __future__ import annotations` for forward-reference compatibility.
- `ruff`-compatible style (double quotes, 88-column limit, imports sorted).
- Conventional Commits message: `feat(utils): ...`.
- DCO `Signed-off-by` footer on the commit.
