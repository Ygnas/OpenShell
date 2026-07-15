# Implementation Summary

## What Was Changed

A new public helper function `sanitize_image_name` was added to the `driver_utils` module in the `openshell-core` crate, along with a corresponding unit test.

### Function: `sanitize_image_name`

```rust
pub fn sanitize_image_name(image: &str) -> String
```

Normalizes a container image reference by applying the following transformations in order:

1. **Trim whitespace** — leading and trailing whitespace is removed via `.trim()`
2. **Lowercase** — the entire string is lowercased via `.to_lowercase()`
3. **Collapse consecutive slashes** — runs of two or more `/` characters are reduced to a single `/` (implemented with a character-by-character pass tracking the previous character)
4. **Strip trailing slash** — any remaining trailing `/` is removed via `.pop()`

### Unit Test: `test_sanitize_image_name`

A `#[cfg(test)]` module `tests` was added at the bottom of the file containing a single test function `test_sanitize_image_name` with five assertions covering:

- A normal image name (`ghcr.io/org/image:latest`) passes through unchanged
- Leading and trailing whitespace is trimmed
- Uppercase characters are lowercased
- Double (consecutive) slashes are collapsed to a single slash
- A trailing slash is stripped

## Files Modified

| File | Change |
|------|--------|
| `crates/openshell-core/src/driver_utils.rs` | Added `sanitize_image_name` function and `#[cfg(test)] mod tests { ... }` block |

## Approach

1. Read the existing `driver_utils.rs` via the GitHub Contents API to understand the existing structure and locate the correct insertion point.
2. Created a new branch `add-sanitize-image-name` branched from `main` using the GitHub Git Refs API.
3. Generated the updated file content in Python (appending the new function and test module after the existing code, under a new section comment).
4. Uploaded the updated file to the branch via the GitHub Contents API (PUT request with base64-encoded content and the original file's blob SHA).
5. Opened a pull request from `add-sanitize-image-name` → `main` via the GitHub Pulls API.

## Pull Request

https://github.com/Ygnas/OpenShell/pull/4
