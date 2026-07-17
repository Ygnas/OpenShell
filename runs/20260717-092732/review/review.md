# PR #12 Review – `feat(utils): add retry_with_backoff helper`

**Repo:** Ygnas/OpenShell  
**Files changed:** `python/openshell/utils/__init__.py`, `python/openshell/utils/http_helpers.py`, `python/openshell/utils/http_helpers_test.py`

---

## Summary

The PR adds a `retry_with_backoff` utility with exponential back-off and jitter, plus nine unit tests. The structure and documentation are solid. Two correctness bugs were found; no callers of renamed/removed symbols exist outside the changed files (entirely new code).

---

## Findings

### Bug 1 – `raise exc from None` corrupts the traceback (line 73, `http_helpers.py`)

**What is wrong:**  
Inside the `except Exception as exc` block, `raise exc from None` is used instead of a bare `raise`. This has two negative effects:
1. It inserts a **spurious extra frame** into the traceback pointing at the `raise exc from None` line itself, making tracebacks noisier and harder to read.
2. It sets `__suppress_context__ = True` and clears `__cause__`, which **silently discards any chained exception context** that debugging tools or logging frameworks would otherwise display.

**Failure scenario:**  
Any caller whose `func` raises (e.g., a `ConnectionError` from a dropped connection) will see a polluted traceback that includes the retry helper's internals as a re-raise point, rather than a clean origination line.

**Fix:**  
Replace `raise exc from None` with a bare `raise` (and adjust the `except` signature accordingly):
```python
except Exception:  # noqa: BLE001
    raise
```

---

### Bug 2 – Jitter is unconditional; `base_delay=0.0` still sleeps up to ~1 s per retry (line 84, `http_helpers.py`)

**What is wrong:**  
The wait formula is:
```python
wait = base_delay * (2**attempt) + random.random()
```
The `random.random()` term (producing a value in `[0, 1)`) is **added unconditionally**, independent of `base_delay`. When a caller passes `base_delay=0.0` (which reads naturally as "no delay"), each retry still sleeps between 0 and 1 second.

**Failure scenario:**  
Any caller using `base_delay=0.0` to speed up retries in integration tests or high-throughput pipelines will be surprised to find that retries introduce up to 1 second of latency per attempt. The unit-test suite never catches this because every retry-path test unconditionally patches `time.sleep`.

**Fix:**  
Scale jitter proportionally to `base_delay` so that zero delay truly means zero:
```python
wait = base_delay * (2**attempt + random.random())  # noqa: S311
```

---

## Non-findings (checked but OK)

- **`max_retries=0`:** Loop runs exactly once, `last_exc` is set, `attempt < max_retries` is `False`, and `last_exc` is raised. Correct.
- **Negative `max_retries`:** Would hit `assert last_exc is not None` (or `TypeError` with `-O`), but this is an unsupported input not documented or tested; not worth an inline comment.
- **`_RETRYABLE_STATUS_CODES` set:** Covers 429, all 5xx codes; appropriate.
- **No callers broken:** This is entirely new code; no existing callers to check.
