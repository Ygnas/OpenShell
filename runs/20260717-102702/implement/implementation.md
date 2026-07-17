# Implementation Summary: `retry_with_backoff` HTTP helper

## Pull Request

**URL:** https://github.com/Ygnas/OpenShell/pull/13  
**Branch:** `add-retry-with-backoff-http-helper` → `main`

---

## What was changed

Two new files were added to the Python SDK under `python/openshell/utils/`:

### 1. `python/openshell/utils/__init__.py` (new)
A minimal package init file that makes `utils` a proper Python sub-package of `openshell`, carrying the standard Apache-2.0 SPDX header used throughout the project.

### 2. `python/openshell/utils/http_helpers.py` (new)
Contains the `retry_with_backoff` function and the supporting `_RETRYABLE_STATUS_CODES` constant.

---

## Function signature

```python
def retry_with_backoff(
    func: Callable[[], httpx.Response],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
```

---

## Approach / design decisions

### Retry trigger
A retry is triggered when the callable returns a response whose `status_code` is in the `_RETRYABLE_STATUS_CODES` frozenset:
- **429** (Too Many Requests)
- **500–511** (all defined 5xx server-error codes)

A retry is also triggered when the callable raises any exception (e.g. `httpx.RequestError` for network-level failures), matching the spirit of the plan.

### Backoff formula
```
wait = base_delay * 2^attempt + random.random()
```
Where `attempt` is zero-indexed (0 on the first retry). `random.random()` returns a float in `[0, 1)`, providing the jitter component that prevents thundering-herd effects when many clients back off simultaneously.

### Success path
The function returns the response immediately as soon as a non-retryable status code is received — no unnecessary looping.

### Exhausted-retries behaviour
- If the callable **raised** an exception on the final attempt, that exception is re-raised, giving the caller full access to the original traceback.
- If the callable **returned a retryable status code** on the final attempt, the response is returned rather than raising, so the caller can inspect headers (e.g. `Retry-After`) or status details.

### Logging
Every retry emits a `WARNING`-level log via `logging.getLogger(__name__)` that includes:
- The exception type or HTTP status code
- The current attempt number out of total (e.g. `1/4`)
- The computed wait time in seconds (2 decimal places)

### Type annotations
`httpx` is imported only under `TYPE_CHECKING` to avoid a hard runtime dependency in environments where `httpx` might not be installed (it is already a project dependency, but the guard is a hygiene best practice).

---

## Files modified

| File | Status | Description |
|---|---|---|
| `python/openshell/utils/__init__.py` | **Created** | Makes `utils` a Python package |
| `python/openshell/utils/http_helpers.py` | **Created** | `retry_with_backoff` implementation |

No existing files were modified.
