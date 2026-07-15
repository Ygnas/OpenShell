# PR #4 Review — Ygnas/OpenShell

**PR Title:** Add sanitize_image_name helper to driver_utils  
**URL:** https://github.com/Ygnas/OpenShell/pull/4  
**Date reviewed:** 2026-07-15

---

## What Was Checked

- Full diff of `crates/openshell-core/src/driver_utils.rs` (+72 lines, 0 deletions)
- The new `pub fn sanitize_image_name(image: &str) -> String` function and its doc comment
- The `#[cfg(test)] mod tests` block with `test_sanitize_image_name`
- Consistency with existing helper functions in the same file (`supervisor_image_tag`, `supervisor_image_should_refresh`) which explicitly handle digest-pinned references
- Correctness of the normalization logic (trim, lowercase, slash collapsing, trailing slash strip)
- Test coverage breadth and edge cases

---

## Issues Found

### Issue 1 — Lowercasing corrupts case-sensitive tag/digest components (Correctness, High)

`to_lowercase()` is applied to the entire image reference string, including the tag portion (e.g. `Ubuntu:Jammy`) and the hex digits of a digest (`@sha256:ABC123…`). Docker image tags are case-sensitive per the OCI Distribution Specification, so silently downcasing them can produce a reference that resolves to a different or non-existent image.

**Fix:** Split the reference on `:` or `@` before lowercasing; only lowercase the registry/repository components (everything before the first `:tag` or `@digest`), or explicitly document that this function only accepts already-lowercase tags and add a check/error for mixed-case input.

---

### Issue 2 — No test or handling for digest-pinned references (Correctness / Test Coverage, Medium)

The rest of `driver_utils.rs` (`supervisor_image_tag`, `supervisor_image_should_refresh`) explicitly treats `@sha256:…` digest references as a distinct case, but `sanitize_image_name` has no test for them and no dedicated logic. Currently a reference like `ghcr.io/org/image@sha256:ABC123` would have its digest hex lowercased — a cosmetically different string that registries may or may not accept depending on implementation, and that breaks round-tripping if the original digest was stored elsewhere.

**Fix:** Add a test case for a digest-pinned reference (e.g. `"ghcr.io/org/image@sha256:abc123DEF"`) and decide explicitly whether the function should pass digests through unchanged or normalize them.

---

### Issue 3 — Unnecessary intermediate heap allocation (Performance / Style, Low)

The function allocates `trimmed` (a full `String` from `image.trim().to_lowercase()`), then immediately iterates over it character-by-character into a second `String result`. This means two heap allocations for every call. The `with_capacity(trimmed.len())` hint is correct in the upper-bound sense (result can only be shorter due to slash collapsing), but the double-allocation is wasteful for hot paths.

**Fix:** Iterate directly over `image.trim().chars()` while applying the lowercase conversion per character (`ch.to_lowercase()`), writing into a single pre-allocated `String`, avoiding the intermediate allocation entirely.

---

## Overall Assessment

The PR adds a useful utility function with a clear doc comment and reasonable basic tests. However, the blanket `to_lowercase()` applied to the entire image reference is a correctness bug for case-sensitive tags and digest references — which the surrounding code in the same file already treats as a special case. The function should not be merged without addressing Issue 1 and Issue 2. Issue 3 is a minor style/performance note that can be addressed in a follow-up.

**Recommendation: Request changes on Issues 1 and 2 before merging.**
