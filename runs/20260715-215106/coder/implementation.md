# Implementation Summary

## What Was Changed

Added a `sanitize_image_name` public helper function to the `openshell-core` crate's driver utilities module. The function normalizes container image references into a canonical form to ensure consistency across the codebase.

## Files Modified

### `crates/openshell-core/src/driver_utils.rs`

Two new functions were added at the end of the file, along with a unit test module:

1. **`pub fn sanitize_image_name(image: &str) -> String`** — the public API that normalizes image names by:
   - Trimming leading/trailing whitespace (`str::trim`)
   - Lowercasing the entire string (`str::to_lowercase`)
   - Collapsing consecutive forward slashes into a single slash (via internal helper)
   - Stripping any trailing slash (`str::trim_end_matches('/')`)

2. **`fn collapse_slashes(s: &str) -> String`** — a private helper that iterates over the characters of the input string and emits a `/` only when the previous character was not already a `/`. This avoids a regex dependency and is straightforward to reason about.

3. **`#[cfg(test)] mod tests`** containing **`fn test_sanitize_image_name`** — covers five cases:
   - A normal image name passes through unchanged
   - Leading/trailing whitespace is trimmed
   - Uppercase letters are lowercased
   - Double slashes are collapsed to a single slash
   - A trailing slash is stripped

## Approach

The implementation follows existing conventions in the file (no external crate dependencies beyond the standard library, doc comments with `///`, inline examples in the doc comment). The function is purely functional with no side effects. The `collapse_slashes` helper is kept private since it is an implementation detail not useful outside of `sanitize_image_name`.

## Branch and Pull Request

- Branch: `add-sanitize-image-name`
- Pull Request: https://github.com/Ygnas/OpenShell/pull/2
- Commit: `9022bc9b752b0c3a98b35866a811e5853701484d`
