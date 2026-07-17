# PR #13 Review — `Add retry_with_backoff helper to utils/http_helpers`

## Summary

The PR adds a new `python/openshell/utils/` package and a `retry_with_backoff`
helper in `http_helpers.py`. The overall design is sound: the exponential +
jitter backoff formula is correct, the loop termination conditions are properly
handled for the normal happy/error paths, the docstring accurately matches the
code, and no existing callers are broken (the function is brand-new with no
callers yet).

Two correctness bugs were found.

---

## Finding 1 — `501 Not Implemented` in the retryable set (Bug)

**File:** `python/openshell/utils/http_helpers.py`, line 20

**What is wrong:**  
`501 Not Implemented` is included in `_RETRYABLE_STATUS_CODES` alongside
transient server errors. HTTP 501 is a *permanent* error: the server is
explicitly stating that it does not implement the requested operation. Retrying
it will produce the same 501 on every subsequent attempt.

**Concrete failure scenario:**  
A caller hits an endpoint that genuinely does not exist on the server (e.g. a
typo in the URL that maps to an unimplemented handler). Instead of propagating
the error immediately, the function burns through all four attempts (with
increasing sleep delays) before returning the 501 response — wasting time,
server quota, and obscuring the real mistake.

**Fix:**  
Remove `501` from `_RETRYABLE_STATUS_CODES`.

---

## Finding 2 — Negative `max_retries` silently skips all calls and hits the "unreachable" sentinel (Bug)

**File:** `python/openshell/utils/http_helpers.py`, line 56

**What is wrong:**  
When `max_retries < 0`, `range(max_retries + 1)` produces an empty sequence.
The loop body never executes, `func()` is never called, `last_exception` stays
`None`, and execution falls through to the supposedly-unreachable block at the
bottom, raising `RuntimeError("retry_with_backoff exhausted retries without a
result")`. This is confusing: the caller gets a cryptic RuntimeError even
though no request was ever attempted.

**Concrete failure scenario:**  
```python
retry_with_backoff(lambda: client.get(url), max_retries=-1)
# Raises RuntimeError instead of ValueError or a response
```

**Fix:**  
Add `if max_retries < 0: raise ValueError("max_retries must be >= 0")` at the
top of the function.

---

## No broken callers

`retry_with_backoff` is a new function with no existing callers in the
repository; no external breakage was found.
