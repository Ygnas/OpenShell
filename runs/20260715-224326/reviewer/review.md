# PR #5 Review — Ygnas/OpenShell

**File:** `crates/openshell-core/src/driver_utils.rs`  
**Change:** Adds `sanitize_image_name` — a function that trims whitespace, lowercases, collapses consecutive slashes, and strips a trailing slash from a container image reference.

---

## Issues Found

### 1. `://` sequences are incorrectly collapsed (bug)

The slash-collapsing loop collapses _every_ pair of consecutive `/` characters into one, including the `//` in scheme prefixes such as `docker://` or `oci://`. Calling `sanitize_image_name("docker://registry/image")` produces `"docker:/registry/image"`, which is a malformed reference.

**Fix:** When the character immediately preceding a `/` is `:`, do not collapse the next `/`.

```rust
for ch in trimmed.chars() {
    if ch == '/' {
        if !last_slash || result.ends_with(':') {
            result.push(ch);
        }
        last_slash = true;
    } else {
        result.push(ch);
        last_slash = false;
    }
}
```

---

### 2. Whitespace-only (or empty) input silently returns `""` (bug)

`sanitize_image_name("   ")` returns an empty string. There is no guard against this, so the empty string will be passed to the container runtime, causing a confusing downstream error instead of an early, explicit failure.

**Fix:** Return `Option<String>` (or `Result<String, _>`) and return `None`/`Err` when the result after trimming and collapsing is empty.

---

### 3. No test covering scheme-prefixed references (missing coverage)

The test suite exercises trim, lowercase, slash-collapse, and trailing-slash removal, but there is no test with a `docker://` or `oci://` style reference. This omission means the bug in issue #1 goes undetected by the test suite.

**Fix:** Add a test such as:

```rust
assert_eq!(
    sanitize_image_name("docker://registry.example.com/org/image:tag"),
    "docker://registry.example.com/org/image:tag"
);
```

---

## Summary

| # | Severity | Description |
|---|----------|-------------|
| 1 | Bug | `://` collapsed to `:/` — scheme-prefixed references are corrupted |
| 2 | Bug | Empty/whitespace input silently produces `""` with no error |
| 3 | Test gap | No coverage for scheme-prefixed references |

Review posted on GitHub as a `COMMENT` (event: `COMMENT`).
