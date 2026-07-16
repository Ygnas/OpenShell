# PR #11 Review — `feat(python): add retry_with_backoff helper to utils/http_helpers.py`

**Repo:** Ygnas/OpenShell  
**Review ID:** 4716789618  
**Status:** COMMENT (changes requested)

---

## Summary

The PR adds a new file `utils/http_helpers.py` introducing `retry_with_backoff(func, max_retries=3, base_delay=1.0)`.  The helper wraps a zero-argument callable, retries on HTTP 429 / 5xx responses, and uses exponential backoff with jitter.  No existing callers were found (new public API).  The overall control-flow logic is correct; the following three issues were identified.

---

## Findings

### 1. Broad `except Exception` retries non-transient errors
**File:** `utils/http_helpers.py`, line 67  
**Severity:** Bug  

The `except Exception` clause catches **every** exception from `func()` — including `TypeError`, `AttributeError`, and any other programming error — and retries it up to `max_retries` times before re-raising.  The docstring only documents retries on HTTP 429/5xx status codes, so the actual contract is broader than advertised, masking bugs in callers.

**Failure scenario:** If `func` raises `TypeError` (e.g. wrong argument type in the callable), the function sleeps and retries 3 times instead of propagating immediately.

**Fix:** Narrow the except to `except (httpx.HTTPStatusError, httpx.TransportError)`, or explicitly document that all exceptions trigger retries.

---

### 2. `raise exc` inside `try` is caught by the same `except` handler
**File:** `utils/http_helpers.py`, line 63  
**Severity:** Bug (structural / latent)  

On line 63, the synthesised `HTTPStatusError` is raised *inside* the `try` block, so the `except Exception` handler on line 67 immediately catches it.  On the final attempt this accidentally works because the handler does a bare `raise`; but the exception travels through the handler unintentionally.  Any future edit to the handler (adding a `continue`, mutating `last_exception`, or catching more specifically) could silently swallow the error.

**Failure scenario:** A future refactor adds `last_exception = exc` inside the except clause *before* the `if attempt == max_retries: raise` guard, which would set `last_exception` to the synthesised error but still re-raise — subtle but fragile.

**Fix:** Restructure so the final-attempt raise occurs *after* the `try/except`, e.g. `break` out of the loop on a retryable status and raise `last_exception` after the loop body.

---

### 3. Unused import: `from typing import Any`
**File:** `utils/http_helpers.py`, line 12  
**Severity:** Warning  

`Any` is imported but never referenced anywhere in the file. Linters (ruff, mypy) will flag this.

**Fix:** Remove `Any` from the import line.

---

## What is correct

- `range(max_retries + 1)` gives the right number of total attempts (1 initial + N retries).
- The wait formula `base_delay * 2**attempt + random.random()` correctly implements exponential backoff with jitter, and the wait is never executed on the final attempt (the `raise` propagates before reaching `time.sleep`).
- Logging at `WARNING` with attempt number and computed wait time is appropriate.
- The `_RETRYABLE_STATUS_CODES` set correctly captures 429 and the full 5xx range.
- No existing callers were broken (new file, no renames/deletions).
