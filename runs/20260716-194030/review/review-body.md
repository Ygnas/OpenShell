## Review of `utils/http_helpers.py` — `retry_with_backoff`

The overall structure is sound and the happy-path / exhausted-retries logic behaves correctly. I found three correctness issues worth fixing before merge.

---

### Finding 1 — Broad `except` retries non-transient errors (inline comment below)

The `except Exception` clause (line 67) catches **every** exception from `func()`, including `TypeError`, `AttributeError`, and other programming errors.  Those will be silently retried `max_retries` times before finally re-raising, masking bugs in the caller and wasting time.  The docstring only advertises retry-on-HTTP-status behaviour, so the contract is also misleading.  Fix: narrow to `except (httpx.HTTPStatusError, httpx.TransportError)` (or at minimum document the broader retry behaviour).

---

### Finding 2 — `raise exc` inside the `try` block is caught by the `except` (inline comment below)

On line 63 the synthesised `HTTPStatusError` is raised *inside* the `try` block, so the `except Exception` handler on line 67 immediately catches it.  On the last attempt this happens to work because the handler does a bare `raise`; but it means the exception travels through the `except` handler unintentionally, and any future edit to the handler (e.g. adding a `continue` or mutating `last_exception`) could silently swallow the error.  Fix: restructure so the final-attempt raise happens *after* the `try/except`, e.g. check `last_exception` outside the loop, or `break` out of the loop and raise below.

---

### Finding 3 — Unused import (inline comment below)

`from typing import Any` (line 12) is imported but never referenced anywhere in the file; linters will flag it and it adds noise.
