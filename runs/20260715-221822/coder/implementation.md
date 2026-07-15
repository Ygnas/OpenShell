# Implementation Summary

## What Was Changed

Added a `sanitize_image_name` public helper function and a corresponding unit test
to the `openshell-core` driver utilities module.

## Files Modified

- **`crates/openshell-core/src/driver_utils.rs`**
  - Added the `sanitize_image_name(image: &str) -> String` public function
  - Added the `test_sanitize_image_name` unit test inside a `#[cfg(test)]` module

No new files were created; the change is a pure addition to an existing file.

## Approach Taken

### Function implementation (`sanitize_image_name`)

The function applies four normalization steps in sequence:

1. **Trim whitespace** — `image.trim()` removes leading and trailing ASCII/Unicode
   whitespace before any other processing.
2. **Lowercase** — `.to_lowercase()` converts the entire reference to lowercase,
   ensuring registry hostnames, image names, and tags are all normalized.
3. **Collapse consecutive slashes** — A single-pass character iterator tracks
   whether the previous character was a `/`; a second consecutive slash is
   skipped rather than appended to the output buffer.
4. **Strip trailing slash** — After the loop, if the last character is `/` it is
   removed with `String::pop()`.

The algorithm runs in O(n) time and avoids allocating intermediate strings (apart
from the single output `String` pre-sized to the trimmed input length).

### Unit test (`test_sanitize_image_name`)

Five cases cover every documented transformation:

| Input | Expected output | Transformation exercised |
|---|---|---|
| `"ubuntu:22.04"` | `"ubuntu:22.04"` | No-op (already canonical) |
| `"  ubuntu:22.04  "` | `"ubuntu:22.04"` | Whitespace trim |
| `"GhCr.Io/Org/Image:Latest"` | `"ghcr.io/org/image:latest"` | Lowercase |
| `"ghcr.io//org/image:latest"` | `"ghcr.io/org/image:latest"` | Double-slash collapse |
| `"ghcr.io/org/image/"` | `"ghcr.io/org/image"` | Trailing-slash strip |

### Branch and PR

- Branch: `add-sanitize-image-name`
- Pull request: https://github.com/Ygnas/OpenShell/pull/3
- Commit message: `Add sanitize_image_name helper to driver_utils.rs`
