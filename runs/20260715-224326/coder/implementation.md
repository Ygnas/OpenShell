# Implementation Summary

## What Was Changed

A new public helper function `sanitize_image_name` was added to the
`openshell-core` crate, along with a corresponding unit test.

## Files Modified

### `crates/openshell-core/src/driver_utils.rs`

Two additions were made at the end of the file:

1. **`pub fn sanitize_image_name(image: &str) -> String`**  
   Normalizes a container image reference by applying four transformations in
   sequence:
   - Trim leading and trailing ASCII whitespace (`str::trim`).
   - Lowercase the entire string (`str::to_lowercase`).
   - Collapse consecutive forward-slashes into a single slash (a single-pass
     character scan that suppresses repeated `/` characters).
   - Strip any remaining trailing slash (`str::trim_end_matches('/')`).

2. **`#[cfg(test)] mod tests { fn test_sanitize_image_name() }`**  
   Five assertions covering each normalization rule:
   - A well-formed image name passes through unchanged.
   - Leading/trailing whitespace is trimmed.
   - Uppercase characters are lowercased.
   - Consecutive slashes (`//`) are collapsed to `/`.
   - A trailing slash is removed.

## Approach

The implementation avoids any external dependencies and relies entirely on
Rust's standard library. Consecutive-slash collapsing is handled with a
single O(n) pass using a boolean flag (`last_slash`) rather than a regex or
repeated string replacements, keeping the logic simple and allocation-minimal.
The function is `pub` so it is accessible from all driver crates that depend
on `openshell-core`.

## Pull Request

https://github.com/Ygnas/OpenShell/pull/5  
Branch: `add-sanitize-image-name` → `main`
