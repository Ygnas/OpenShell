# Code Review: Ygnas/OpenShell PR #2

## PR Title
Add sanitize_image_name helper to driver_utils.rs

## What Was Checked

- The diff for `crates/openshell-core/src/driver_utils.rs`
- The public function `sanitize_image_name(image: &str) -> String` and its documented behavior
- The private helper `collapse_slashes(s: &str) -> String`
- The unit test `test_sanitize_image_name` covering 5 cases

## Issues Found

### Issue 1: Lowercasing corrupts case-sensitive tags and digest references (Severity: High)

**What is wrong:** `to_lowercase()` is applied to the entire image string, including the tag/digest portion after `:` or `@`. Docker image tags are case-sensitive, and digest references like `sha256:ABCDEF...` are case-sensitive hex strings — lowercasing them silently corrupts the reference and will break registry lookups.

**How to fix:** Only lowercase the registry/repository portion (everything before the first `:` or `@`), leaving the tag or digest suffix unchanged.

---

### Issue 2: `collapse_slashes` is an unnecessary hand-rolled helper (Severity: Low)

**What is wrong:** The manual char-by-char loop in `collapse_slashes` is more complex than necessary and harder to read at a glance.

**How to fix:** Replace with a concise iterator expression, e.g.:
```rust
fn collapse_slashes(s: &str) -> String {
    s.split('/').filter(|p| !p.is_empty()).collect::<Vec<_>>().join("/")
}
```
Or inline it entirely into `sanitize_image_name` to reduce indirection.

---

### Issue 3: Missing edge-case tests (Severity: Medium)

**What is wrong:** The test suite does not cover:
- Empty string input (`""`)
- Whitespace-only input (`"   "`)
- Images with digest references (`ghcr.io/org/image@sha256:ABCDEF...`), which would expose the lowercasing bug

**How to fix:** Add test cases for these inputs and define expected outputs explicitly; the digest test in particular would have caught Issue 1 before merge.

---

## Overall Assessment

The PR is **not ready to merge** in its current form. The most critical problem is Issue 1: unconditional lowercasing of the entire image string is semantically incorrect for Docker image references and will silently break digest-pinned images. The helper utility and its tests need to be revised before this function can be safely used by callers.
