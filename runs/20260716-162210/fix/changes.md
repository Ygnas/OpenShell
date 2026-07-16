# Changes Made to Address PR #9 Review Comments

**PR:** https://github.com/Ygnas/OpenShell/pull/9  
**Branch:** `add-retry-with-backoff-helper`  
**Commit:** `18d04af` — _Address review feedback: remove 501, drop dead last_exception, extract _compute_backoff_  
**File modified:** `utils/http_helpers.py`

---

## Issue 1 — Removed `501` from `_RETRYABLE_STATUS_CODES`

**What changed:**  
```python
# Before
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 501, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511})

# After
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504, 505, 506, 507, 508, 509, 510, 511})
```

**Why:** `501 Not Implemented` is a **permanent** server response indicating that the server does not support the requested method or endpoint. Retrying the exact same request against a server that has explicitly declared it does not implement that operation will never succeed — it only wastes resources and delays failure reporting. All other codes in the set (`429`, `500`, `502`–`511`) represent transient conditions (rate limits, temporary overloads, gateway errors) where a retry has a reasonable chance of succeeding.

---

## Issue 2 — Deleted dead `last_exception` variable

**What changed:**  
Removed the declaration `last_exception: BaseException | None = None` and the assignment `last_exception = exc` inside the `except` block.

**Why:** The variable was written on every caught exception but never subsequently read. The final re-raise in the exhausted-retries path is a bare `raise` statement, which re-propagates the currently-active exception object directly without ever consulting `last_exception`. The dead variable was misleading — it implied the variable would be used later — and introduced unnecessary noise. Removing it makes the control flow clearer.

---

## Issue 3 — Extracted `_compute_backoff(attempt, base_delay)` helper

**What changed:**  
Added a new module-private function:
```python
def _compute_backoff(attempt: int, base_delay: float) -> float:
    """Return exponential backoff delay with uniform jitter.

    Formula: ``base_delay * 2^attempt + random(0, 1)``
    """
    return base_delay * (2 ** attempt) + random.random()  # noqa: S311
```

Replaced both inline occurrences of `base_delay * (2 ** attempt) + random.random()` (one in the `except` branch, one in the retryable-status branch) with calls to `_compute_backoff(attempt, base_delay)`.

**Why:** The identical backoff formula was copy-pasted in two places. Any future change to the strategy — adding a `max_delay` cap, switching to full jitter, or changing the exponent base — would have had to be applied in both locations, making silent divergence likely. Centralising the formula in a single named helper eliminates that risk and also makes the intent of the call sites immediately obvious.
