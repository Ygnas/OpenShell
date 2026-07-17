# PR #12 Review — Changes Made

**File edited:** `python/openshell/utils/http_helpers.py`  
**Commit:** `7b641c17`  
**Branch:** `feat/retry-with-backoff-http-helper`

---

## Bug 1 — Traceback corruption: `raise exc from None` → bare `raise` (line 72–73)

### What changed
```python
# Before
except Exception as exc:  # noqa: BLE001
    raise exc from None

# After
except Exception:  # noqa: BLE001
    raise
```

### Why
`raise exc from None` has two problems:
1. It adds an extra traceback frame pointing at the re-raise line itself, making tracebacks harder to read.
2. It sets `__suppress_context__ = True`, which silently drops any chained exception context — information that debuggers and logging frameworks would otherwise surface.

A bare `raise` re-raises the active exception completely unchanged, preserving the full, unmodified traceback.

---

## Bug 2 — Unconditional jitter causes sleep even when `base_delay=0.0` (line 84)

### What changed
```python
# Before
wait = base_delay * (2**attempt) + random.random()  # noqa: S311

# After
wait = base_delay * (2**attempt + random.random())  # noqa: S311
```

### Why
The original formula added `random.random()` (a value in [0, 1)) as a flat addend independent of `base_delay`. A caller passing `base_delay=0.0` to suppress all sleeping would still block up to ~1 second per retry in production. The test suite never caught this because every retry-path test patches `time.sleep`.

Moving `random.random()` inside the `base_delay *` factor makes jitter proportional to the base delay: if `base_delay=0.0`, the entire wait expression evaluates to `0.0`. The behaviour for positive base delays is essentially unchanged (jitter is still a sub-interval of `base_delay`).

---

## Docstring update (line 48)

The inline formula in the `Args` block was updated from  
`base_delay * 2**n + random(0, 1)` to `base_delay * (2**n + random(0, 1))`  
to accurately reflect the corrected implementation.
