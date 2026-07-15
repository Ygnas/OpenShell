# PR #4 Review Feedback — Changes Summary

**PR:** https://github.com/Ygnas/OpenShell/pull/4  
**Branch:** `add-sanitize-image-name`  
**Fix commit:** `8a87425f9fc6fa35c6a2c6c4939d34932310f55d`  
**File modified:** `crates/openshell-core/src/driver_utils.rs`

---

## Issue 1 — Lowercasing corrupted case-sensitive tag/digest components

**Problem:** The original implementation called `to_lowercase()` on the entire image
reference string, including the tag and digest portions. Container image tags are
case-sensitive by the OCI distribution spec (e.g. `Ubuntu:Jammy`) and digest hex
strings must be preserved exactly (e.g. `@sha256:ABC123...`). Lowercasing them
changes the string without producing a valid canonical form.

**Fix:** Before normalizing, the reference is split into two parts:
- **repo part** — everything before the first `@` (digest separator) or before the
  last `:` that appears in the name component (not in a registry port, e.g.
  `registry:5000/image`).
- **suffix** — the `@sha256:...` digest or `:tag` string, preserved verbatim.

Only the repo part is lowercased and slash-collapsed. The suffix is re-attached
unchanged. For example:
- `GHCR.IO/Org/Image:Jammy` → `ghcr.io/org/image:Jammy`
- `ghcr.io/org/image@sha256:abc123DEF` → `ghcr.io/org/image@sha256:abc123DEF`

---

## Issue 2 — No test for digest-pinned references

**Problem:** The rest of `driver_utils.rs` (`supervisor_image_tag`,
`supervisor_image_should_refresh`) explicitly handles `@sha256:...` references as a
distinct case, but `sanitize_image_name` had no test or logic for them. The original
code would silently lowercase the digest hex without any normalization benefit.

**Fix:** Two new test assertions were added to `test_sanitize_image_name`:
1. A digest-pinned reference with a lowercase repo — verifies the digest hex is
   left unchanged.
2. A digest-pinned reference with an uppercase repo — verifies the repo is lowercased
   while the digest is preserved verbatim.

---

## Issue 3 — Unnecessary intermediate allocation and extra pass

**Problem:** The original code allocated a full lowercased `String` (`trimmed`) via
`to_lowercase()` on the entire input, and then iterated over it character-by-character
in a second pass to collapse slashes. This produced two heap allocations for what
could be done in one.

**Fix:** The `to_lowercase()` call is now applied only to `repo_part` (already a
sub-slice of the trimmed input), and the result is iterated once in-place. The
capacity hint uses `image.len()` (the trimmed full reference length), which is the
tightest safe upper bound since slash-collapsing can only shorten the repo part and
the suffix is appended after. This eliminates the extra full-string allocation and
reduces the work to a single character-level pass over the repository portion only.
