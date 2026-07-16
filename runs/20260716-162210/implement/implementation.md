# Implementation Summary

## Pull Request

**Title**: Add retry_with_backoff helper to utils/http_helpers.py  
**URL**: https://github.com/Ygnas/OpenShell/pull/9  
**Branch**: `add-retry-with-backoff-helper` → `main`  
**Commit**: `9f40edd07d0b3ec5876b08545c255a7a54a7502c`

---

## Files Modified

| File | Change |
|------|--------|
| `utils/http_helpers.py` | **Created** (new file — 109 lines) |

No existing files were modified.

---

## What Was Changed

### `utils/http_helpers.py` (new file)

A new module providing HTTP utility helpers for OpenShell.  It exports a
single public function:

```python
def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Any:
```

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `func` | — | Zero-argument callable that performs an HTTP request and returns a response object with a `status_code` attribute. |
| `max_retries` | `3` | Maximum number of retry attempts after the initial call fails. |
| `base_delay` | `1.0` | Base delay in seconds used to compute the exponential back-off interval. |

#### Behaviour

- **Retryable status codes**: `429` (Too Many Requests) and all `5xx` codes
  (500–511).  Exceptions raised by `func` are also retried.
- **Backoff formula**: `base_delay * 2^attempt + random.random()` — full
  exponential backoff with uniform jitter in `[0, 1)` added to each interval,
  matching the spec `base_delay * 2^attempt + random(0, 1)`.
- **Return**: the response object when `func` returns a non-retryable status
  code.
- **Exhausted retries**: raises the last exception propagated by `func`, or a
  `RuntimeError` describing the last retryable status code if `func` kept
  returning bad responses rather than raising.
- **Logging**: `WARNING`-level log per retry attempt with the attempt number
  and computed wait time; `ERROR`-level log when all retries are exhausted.

#### Dependencies

Only Python standard-library modules are used (`logging`, `random`, `time`),
so no new package dependencies are introduced.

---

## Approach

The implementation uses a **single `for attempt in range(max_retries + 1)`
loop** so that the initial attempt and all subsequent retries share identical
exception-handling and status-code-checking logic, avoiding duplication.

On each iteration:
1. `func()` is called inside a `try/except`.
2. If it raises, the exception is caught; if this was the last allowed attempt
   the exception is re-raised, otherwise a wait time is computed and
   `time.sleep()` is called before the next iteration.
3. If it returns a response whose `status_code` is not in the retryable set,
   the response is returned immediately.
4. If the status code *is* retryable and attempts remain, the wait time is
   computed and `time.sleep()` is called; if no attempts remain a
   `RuntimeError` is raised.

The SPDX licence header (`Apache-2.0`) consistent with all other Python files
in the repository was included at the top of the new file.
