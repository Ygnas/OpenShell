# Implementation Summary

## Pull Request

**URL:** https://github.com/Ygnas/OpenShell/pull/7  
**Branch:** `fix/erofs-readonly-submount-chown` → `main`  
**Title:** Fix recursive chown to skip read-only submounts and handle EROFS gracefully

---

## Problem Being Fixed

During sandbox startup, the Kubernetes driver injects `OPENSHELL_SANDBOX_UID`/`OPENSHELL_SANDBOX_GID` environment variables. The supervisor then calls `chown_sandbox_home` to recursively change ownership of `/sandbox` to the injected UID/GID.

If any sub-path under `/sandbox` is backed by a `readOnly: true` Kubernetes volume, the `chown(2)` syscall returns `EROFS` (read-only file system). The original code propagated this error directly, causing the supervisor to abort with a fatal error and leaving the pod in `CrashLoopBackOff`.

---

## Files Modified

| File | Change |
|------|--------|
| `crates/openshell-supervisor-process/src/process.rs` | Added `is_readonly_mount` helper; rewrote `chown_sandbox_home` to skip read-only mount subtrees and handle `EROFS` gracefully on files |

No new Cargo dependencies were added. The implementation uses only `std` and the `nix` crate already present in the crate's `Cargo.toml`.

---

## Approach

### 1. `is_readonly_mount(path: &Path) -> std::io::Result<bool>`

A new `#[cfg(unix)]` helper function added directly above `chown_sandbox_home` in `process.rs`.

**How it works:**
- Calls `path.canonicalize()` to resolve symlinks.
- Opens `/proc/self/mountinfo` and iterates over lines.
- Parses each line per the mountinfo format:  
  `<mount_id> <parent_id> <major:minor> <root> <mount_point> <mount_options> ...`
- Finds the **longest-matching mount point** that is a prefix of the canonical path (to handle nested mounts correctly).
- Returns `Ok(true)` if the best-matching mount's options contain the `ro` flag; `Ok(false)` otherwise.
- Returns `Ok(false)` (non-fatal) if no mount entry matches (defensive default).

### 2. Modified `chown_sandbox_home`

The recursive chown function was extended with two new behaviours:

**a) Skip read-only mount subtrees:**  
Before recursing into a child directory, `is_readonly_mount` is called. If the directory is a read-only mount point, the entire subtree is skipped with a `debug!` log message. This prevents `EROFS` errors from propagating.

**b) Ignore `EROFS` on files:**  
For file entries (non-directories), `chown` is matched on its result:
- `Ok(())` → continue normally.
- `Err(EROFS)` → log a debug message and continue (non-fatal).
- `Err(other)` → propagate as a fatal error (same as before).

This secondary defence handles the case where a file lives inside a read-only filesystem but its parent directory was not itself detected as a mount point boundary by `is_readonly_mount`.

**Unchanged behaviour:**
- The initial `chown(root, ...)` on `/sandbox` itself is still fatal if it fails — a read-only root is a genuine misconfiguration.
- Symlinks are still rejected/skipped identically to before.
- All non-`EROFS` errors on files still abort startup.

### 3. Documentation

Both `is_readonly_mount` and `chown_sandbox_home` were given comprehensive doc comments explaining the purpose, invariants, and edge-case handling.

---

## Edge Cases

| Scenario | Behaviour |
|----------|-----------|
| `/sandbox` itself is read-only | `chown(root)` fails → error propagated → supervisor aborts (intended) |
| Nested read-only mounts | Longest-match logic picks the deepest mount; full subtree is skipped |
| File in read-only filesystem (no mount point boundary) | `EROFS` ignored, walk continues |
| Symlinks (root or children) | Rejected/skipped as before; no behaviour change |
| Non-Linux platforms | `is_readonly_mount` is `#[cfg(unix)]`; `/proc/self/mountinfo` is Linux-specific but the `#[cfg(unix)]` gate on `chown_sandbox_home` itself means this only compiles/runs on Unix targets |
| `/proc/self/mountinfo` unavailable | `is_readonly_mount` returns `Err`; `unwrap_or(false)` in the caller treats it as "not read-only" and proceeds normally |
