# Changes made to address PR #13 review feedback

**File modified:** `python/openshell/utils/http_helpers.py`
**Commit:** `f9a46e14`
**Branch:** `add-retry-with-backoff-http-helper`

---

## Fix 1 — Remove `501` from `_RETRYABLE_STATUS_CODES` (line 20)

### What changed
`501` was removed from the `_RETRYABLE_STATUS_CODES` frozenset.

**Before:**
```python
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset(
    {429, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511}
)
```
**After:**
```python
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset(
    {429, 500, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511}
)
```

### Why
HTTP 501 Not Implemented indicates that the server does not and will
never support the requested method. This is a permanent client/server
incompatibility, not a transient condition. Retrying a 501 wastes
quota and causes the caller to wait unnecessarily before seeing the
same failure again. Unlike 500 (Internal Server Error) or 503 (Service
Unavailable), a 501 cannot resolve itself on a subsequent attempt.

---

## Fix 2 — Guard against negative `max_retries` (line 54, inserted)

### What changed
A `ValueError` guard was added at the top of `retry_with_backoff`,
before any state initialisation or looping.

**Inserted:**
```python
if max_retries < 0:
    raise ValueError("max_retries must be >= 0")
```

### Why
When `max_retries` is negative, `range(max_retries + 1)` evaluates to
an empty range. The loop body never executes, `func()` is never called,
`last_exception` remains `None`, and the function falls through to the
`raise RuntimeError("retry_with_backoff exhausted retries without a
result")` sentinel — a misleading error that says retries were
*exhausted* when in fact *no attempt was ever made*.

Raising `ValueError` immediately at function entry:
- Fails fast with a clear, accurate message.
- Follows the Python convention of validating arguments before doing
  any work.
- Makes the "unreachable" sentinel at the bottom truly unreachable for
  all valid inputs.
