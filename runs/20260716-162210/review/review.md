# PR #9 Review — `utils/http_helpers.py`

## Summary

The `retry_with_backoff` helper is well-structured and well-documented overall,
but three concrete issues need to be addressed before merging.

---

## Issue 1 — `501 Not Implemented` is not a retryable status code

**File:** `utils/http_helpers.py`, line 20

```python
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 501, 502, 503, 504, ...})
```

`501 Not Implemented` is a **permanent** client-facing error: the server is
declaring that it does not support the requested method or feature. Retrying
the same request will never produce a different outcome.

**Fix:** Remove `501` from `_RETRYABLE_STATUS_CODES`.

```python
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511})
```

---

## Issue 2 — `last_exception` is assigned but never read (dead code)

**File:** `utils/http_helpers.py`, lines 56 & 60

```python
last_exception: BaseException | None = None
...
last_exception = exc          # assigned here …
if attempt == max_retries:
    ...
    raise                     # … but bare `raise` re-raises `exc` directly
```

`last_exception` is written on every caught exception but is never subsequently
read; the final re-raise uses a bare `raise`, which already propagates the
current exception. The variable is pure noise and misleads readers into
thinking it is used.

**Fix:** Delete the `last_exception: BaseException | None = None` declaration
and the `last_exception = exc` assignment.

---

## Issue 3 — Backoff formula is duplicated across two branches

**File:** `utils/http_helpers.py`, lines 65 and 89

```python
# exception branch
wait_time = base_delay * (2 ** attempt) + random.random()

# retryable-status branch
wait_time = base_delay * (2 ** attempt) + random.random()
```

The identical formula is copy-pasted in both the `except` block and the
retryable-status-code block. Any future change (e.g. adding a `max_delay`
cap or switching to full jitter) must be applied in two places, making
divergence likely.

**Fix:** Refactor the loop so both retryable paths share a single computation —
for example, `continue` into a shared tail that computes `wait_time` and
sleeps, or extract a small `_compute_backoff(attempt, base_delay)` helper.

