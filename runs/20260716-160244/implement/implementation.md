# Implementation Summary

## Overview

This change fixes a bug where the supervisor's recursive `chown /sandbox`
operation fails with `EROFS` when a read-only sub-mount (e.g. a Kubernetes
`readOnly: true` volume) exists under `/sandbox`, causing the sandbox to crash
at startup and the pod to enter `CrashLoopBackOff`.

## Pull Request

**URL:** https://github.com/Ygnas/OpenShell/pull/8  
**Branch:** `fix/skip-readonly-submounts-chown`  
**Base:** `main`

---

## Files Modified

### 1. `crates/openshell-supervisor-process/src/mount.rs` *(new)*

New module providing a read-only mount-point detector.

**Key exports:**
- `pub fn get_readonly_mount_points() -> std::io::Result<HashSet<PathBuf>>`  
  Parses `/proc/self/mountinfo` and returns every mount point whose
  per-mount options include the bare `ro` token (comma-split, exact match to
  avoid false positives on options like `proto` or `noro`).
- `pub(crate) fn get_readonly_mount_points_from(path: &str)`  
  Testable inner function that accepts an arbitrary file path, allowing unit
  tests to inject synthetic mountinfo content without touching `/proc`.

**Tests in this file:**
- `detects_readonly_mount_point` — confirms `ro,relatime` is detected
- `excludes_readwrite_mount_point` — confirms `rw,relatime` is not detected
- `handles_mixed_mount_points` — multiple entries with mixed RO/RW
- `skips_malformed_lines` — lines with fewer than 6 fields are silently ignored
- `does_not_false_positive_on_option_containing_ro_substring` — `proto`, `noro` do not trigger

---

### 2. `crates/openshell-supervisor-process/src/lib.rs` *(modified)*

Added `pub mod mount;` to register the new module.

---

### 3. `crates/openshell-supervisor-process/src/process.rs` *(modified)*

**Import added:**
```rust
#[cfg(unix)]
use crate::mount::get_readonly_mount_points;
```

**`chown_sandbox_home` function — updated signature and body:**

Before:
```rust
fn chown_sandbox_home(root: &Path, uid: Option<Uid>, gid: Option<Gid>) -> Result<()>
```

After:
```rust
fn chown_sandbox_home(
    root: &Path,
    uid: Option<Uid>,
    gid: Option<Gid>,
    ro_mounts: &std::collections::HashSet<std::path::PathBuf>,
) -> Result<()>
```

Behavioural changes:
1. **Pre-filter**: If `ro_mounts.contains(root)`, logs `info!` and returns
   `Ok(())` without chowning or descending — the entire subtree is skipped.
2. **EROFS handling**: `chown` now matches on `nix::errno::Errno::EROFS`;
   instead of propagating it, the function logs `warn!` and continues.
3. **Recursive call**: Passes `ro_mounts` down to child calls.

**`prepare_filesystem` function — updated:**

Before the recursive `chown_sandbox_home(sandbox_home, uid, gid)?` call,
`get_readonly_mount_points()` is called once and the result is passed through.
`unwrap_or_default()` is used so non-Linux environments (where
`/proc/self/mountinfo` does not exist) get an empty set and the function
behaves as before.

```rust
let ro_mounts = get_readonly_mount_points().unwrap_or_default();
info!(?uid, ?gid, "Chowning /sandbox for driver-injected UID/GID");
chown_sandbox_home(sandbox_home, uid, gid, &ro_mounts)?;
```

**Existing tests updated:**

All three existing tests that call `chown_sandbox_home` directly now pass
an empty `HashSet` as the `ro_mounts` argument. This preserves their existing
semantics exactly.

**New test added:**

`chown_sandbox_home_skips_readonly_mount_subtree` — creates a temporary
directory tree with a simulated read-only sub-directory (added to the
`ro_mounts` set), writes a file inside it, runs `chown_sandbox_home`, and
asserts that the file's ownership was not changed.

---

### 4. `CHANGELOG.md` *(new)*

Documents the fix in Keep-a-Changelog format under `[Unreleased]`.

---

## Approach

The implementation follows the plan closely but uses the existing recursive
`std::fs::read_dir` pattern rather than introducing the `walkdir` crate (the
codebase already uses this pattern in `chown_sandbox_home`). This keeps the
diff minimal and avoids adding a new dependency.

The three-layer strategy:
1. **Detect**: Parse `/proc/self/mountinfo` once before the walk, building a
   `HashSet<PathBuf>` of read-only mount points. Lookup is O(1) per path.
2. **Skip**: When `chown_sandbox_home` visits a directory that is in the set,
   log and return immediately — neither the directory nor any of its children
   are chowned.
3. **Tolerate**: If `chown` still returns `EROFS` (e.g. a non-directory file
   inside an RO mount that was not itself a known mount point), log a warning
   and continue rather than aborting.

This is backward-compatible: existing behaviour for fully read-write trees is
unchanged. No new mandatory dependencies were added to `Cargo.toml`.
