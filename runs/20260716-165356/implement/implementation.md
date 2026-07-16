# Implementation Summary

## Pull Request

**URL:** https://github.com/Ygnas/OpenShell/pull/10  
**Title:** Add retry_with_backoff helper to utils/http_helpers.py  
**Branch:** `add-retry-with-backoff-http-helper` → `main`

---

## What Was Changed

### New file: `utils/http_helpers.py`

A new Python module was created at the repository root under `utils/http_helpers.py`. This is the only file modified in this change.

---

## Approach Taken

### Function signature

```python
def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
):
```

The function accepts:
- `func` — a zero-argument callable that performs an HTTP request and returns a response object exposing a `status_code` attribute (compatible with both `httpx.Response` and `requests.Response`).
- `max_retries` — maximum number of retry attempts after the initial call (default `3`, so the callable is invoked at most 4 times total).
- `base_delay` — base delay in seconds used for the exponential backoff formula (default `1.0`).

### Retry logic

Retries are triggered for two categories of HTTP status codes:
- **429** — Too Many Requests (rate limiting)
- **5xx** — Server errors: 500, 502, 503, 504

These are stored in a module-level `frozenset` named `_RETRYABLE_STATUS_CODES` for O(1) lookup.

### Backoff formula

For each retry attempt `n` (0-indexed, so the first retry is attempt 0):

```
wait = base_delay * 2**attempt + random.uniform(0, 1)
```

This matches the plan specification exactly:
`base_delay * 2^attempt + random(0, 1)`

The jitter (`random.uniform(0, 1)`) prevents thundering-herd effects when many callers retry simultaneously.

### Logging

Every retry is logged at `WARNING` level via the standard `logging` module using a module-level logger (`logging.getLogger(__name__)`). The log message includes:
- The current attempt number (1-indexed for readability)
- The total number of retries configured
- The triggering HTTP status code **or** the exception message
- The computed wait time in seconds (formatted to 2 decimal places)

### Return / raise semantics

- If `func` returns a **non-retryable** status code, the response is returned immediately.
- If all retries are exhausted and the last call returned a **retryable** status code, that response is returned to the caller so it can inspect it (e.g. read the `Retry-After` header or log the body).
- If `func` **raises an exception** and retries are exhausted, the exception is re-raised using a bare `raise` (preserving the original traceback).
- If `func` raises on an intermediate attempt, the exception is caught, a retry warning is logged, and the loop continues.

### Module structure

- **SPDX license header** — matches the repo convention (`Apache-2.0`, `Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES`).
- `from __future__ import annotations` — matches the coding style used throughout the Python codebase.
- Standard-library-only imports (`logging`, `random`, `time`, `typing`) — no new dependencies introduced.
- Full NumPy-style docstring with `Parameters`, `Returns`, and `Raises` sections.

---

## Files Modified

| File | Change |
|------|--------|
| `utils/http_helpers.py` | **New file** — `retry_with_backoff` helper function |

No existing files were modified.
