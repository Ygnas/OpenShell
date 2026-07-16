# Implementation Summary

## What Was Changed

A new Python helper module was created as described in the implementation plan.

### Files Modified

| File | Action |
|------|--------|
| `utils/http_helpers.py` | **Created** — new module containing the `retry_with_backoff` helper |

No existing files were modified.

---

## Approach

### Function Signature

```python
def retry_with_backoff(
    func: Callable[[], httpx.Response],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> httpx.Response:
```

- `func` — a zero-argument callable that performs an HTTP request and returns an `httpx.Response`.
- `max_retries` — total number of retry attempts after the initial call (default `3`).
- `base_delay` — base delay in seconds for the backoff calculation (default `1.0`).

### Retry Logic

Retryable status codes are defined as a module-level set:

```python
_RETRYABLE_STATUS_CODES = {429} | set(range(500, 600))
```

The main loop runs `max_retries + 1` times (initial attempt plus retries).  After each non-final failed attempt (either a retryable HTTP status or a raised exception), the helper:

1. Computes the wait time: `base_delay * 2^attempt + random(0, 1)`
2. Logs a `WARNING` message with the attempt number, wait duration, and reason.
3. Sleeps for the computed interval.

On the final attempt the exception (or a synthesised `httpx.HTTPStatusError` for a retryable status) is re-raised directly to the caller.

### Backoff Formula

```
wait = base_delay * 2^attempt + random.random()
```

- `attempt=0` (first retry): `base_delay * 1 + jitter`
- `attempt=1` (second retry): `base_delay * 2 + jitter`
- `attempt=2` (third retry): `base_delay * 4 + jitter`

The jitter (`random.random()` → uniform `[0, 1)`) prevents thundering-herd problems when many clients retry simultaneously.

### Logging

Each retry is logged at `WARNING` level via the standard `logging` module:

```
WARNING:utils.http_helpers:Retry attempt 1/3 after 1.42s (reason: HTTP 429)
```

### Return and Exception Behaviour

- Returns the `httpx.Response` on the first successful (non-retryable status) response.
- Re-raises the last exception (raised by `func` **or** a synthesised `HTTPStatusError`) after exhausting all retries.

---

## Pull Request

- **Branch:** `feat/add-retry-with-backoff-http-helper`
- **PR URL:** https://github.com/Ygnas/OpenShell/pull/11
- **Commit:** `bc5a3d0ef38827d03d813b1590c10d1ee8eb3618`
