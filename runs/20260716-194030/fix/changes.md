# Changes made to address PR #11 review feedback

**File changed:** `utils/http_helpers.py`  
**Branch:** `feat/add-retry-with-backoff-http-helper`  
**Commit:** `00b84c1`

---

## Finding 1 — Narrowed the `except` clause

**Problem:** `except Exception` retried on every exception, including programming errors like `TypeError` and `AttributeError`. These are not transient and should never be retried; retrying them wastes time and masks bugs in the caller. The docstring only documented HTTP-status and transport retries, making the contract misleading.

**Fix:** Changed `except Exception` to `except (httpx.HTTPStatusError, httpx.TransportError)`. Only genuine transient failures (bad HTTP status codes and network-level errors) are now caught and retried. Programming errors propagate immediately. Updated the `Raises:` docstring section to reflect the narrowed contract.

---

## Finding 2 — Moved final `raise` outside the `try/except` block

**Problem:** The synthesised `HTTPStatusError` (for retryable status codes) was raised with `raise exc` *inside* the `try` block on the last attempt. Because the `except Exception` handler followed immediately, it caught that raise unintentionally. On the last attempt this happened to work (bare `raise` re-raised it), but any future edit to the handler—like adding `continue` or mutating `last_exception`—could silently swallow the error.

**Fix:** Removed the in-loop `raise`. The synthesised exception is now stored in `last_exception` just like the transport-error path. An `if attempt == max_retries: break` exits the loop without entering the sleep/log block, and a single `raise last_exception` after the loop raises it cleanly—completely outside any `except` handler. This also removes the now-unreachable `raise RuntimeError(...)` guard.

---

## Finding 3 — Removed unused `from typing import Any` import

**Problem:** `from typing import Any` was present on line 12 but `Any` was never referenced anywhere in the file. Linters (e.g. `ruff`, `flake8`) flag this as an unused import.

**Fix:** Deleted the `from typing import Any` line entirely.
