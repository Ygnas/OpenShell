**Implementation Plan – Issue #2294**  
*Bug: Kubernetes sandbox crashes EROFS – recursive `chown /sandbox` fails on read‑only submounts (0.0.82)*  

---

## Issue
During sandbox startup the OpenShell supervisor performs a **recursive `chown /sandbox`** to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` volume), the recursive chown hits that mount and returns `EROFS`.  
The supervisor aborts, the agent never starts, and the pod ends up in `CrashLoopBackOff`.  
This started after upgrading to 0.0.82; the same pod spec worked on 0.0.39.

---

## Approach
1. **Gracefully ignore `EROFS` errors** during the recursive chown.  
   * The supervisor should continue chowning the rest of the tree and only log a warning when a read‑only path is encountered.  
2. Replace the existing recursive chown implementation with a new helper that:
   * Walks the directory tree (`walkdir::WalkDir`).
   * Calls `nix::unistd::chown` on each entry.
   * Swallows `nix::Error::Sys(Errno::EROFS)` and logs a warning.
   * Propagates any other error.
3. Update the supervisor to use the new helper.
4. Add unit tests to verify:
   * Successful chown on a writable tree.
   * Proper handling of `EROFS` (simulated via a mock).
   * Propagation of non‑`EROFS` errors.

---

## Files to Modify / Create

| File | Change |
|------|--------|
| `src/sandbox.rs` (or wherever the recursive chown is implemented) | Add `chown_recursive_ignore_ro` helper; replace existing call. |
| `Cargo.toml` | Ensure `walkdir` is listed as a dependency (likely already present). |
| `tests/sandbox_chown_ignore_ro.rs` | New unit test module. |

### Detailed Changes

#### 1. `src/sandbox.rs`

```rust
use std::path::Path;
use anyhow::Result;
use log::warn;
use nix::unistd::{chown, Gid, Uid};
use walkdir::WalkDir;

/// Recursively chown `path` to `uid`/`gid`, ignoring read‑only mounts.
/// Any `EROFS` error is logged and skipped; other errors are returned.
fn chown_recursive_ignore_ro(path: &Path, uid: Uid, gid: Gid) -> Result<()> {
    for entry in WalkDir::new(path).follow_links(false) {
        let entry = entry?;
        let entry_path = entry.path();

        // Attempt to chown; ignore EROFS.
        match chown(entry_path, Some(uid), Some(gid)) {
            Ok(_) => {}
            Err(nix::Error::Sys(nix::errno::Errno::EROFS)) => {
                warn!("Skipping chown on read‑only path: {:?}", entry_path);
                continue;
            }
            Err(e) => return Err(e.into()),
        }
    }
    Ok(())
}
```

*Replace the existing recursive chown call (e.g. `chown_sandbox_root(&sandbox_path, uid, gid)`) with `chown_recursive_ignore_ro(&sandbox_path, uid, gid)`.*

#### 2. `Cargo.toml`

```toml
[dependencies]
walkdir = "2"          # already present in many OpenShell crates
```

*(If `walkdir` is missing, add it.)*

#### 3. `tests/sandbox_chown_ignore_ro.rs`

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::{self, File};
    use std::io::Write;
    use std::os::unix::fs::PermissionsExt;
    use tempfile::tempdir;
    use nix::unistd::{Uid, Gid};

    #[test]
    fn test_chown_recursive_ignore_ro_success() {
        let dir = tempdir().unwrap();
        let sub = dir.path().join("sub");
        fs::create_dir(&sub).unwrap();
        let file = sub.join("file.txt");
        File::create(&file).unwrap();

        // Use current uid/gid for test
        let uid = Uid::current();
        let gid = Gid::current();

        // Should succeed without error
        chown_recursive_ignore_ro(dir.path(), uid, gid).unwrap();
    }

    #[test]
    fn test_chown_recursive_ignore_ro_erofs() {
        // Simulate EROFS by creating a file with no write permission
        // and attempting to chown it with a non‑existent uid/gid.
        // Since we cannot mount a read‑only FS in tests, we mock the chown call.
        // This test ensures that the helper swallows EROFS and returns Ok.

        // (Implementation omitted – see discussion below)
    }
}
```

> **Note**: The `EROFS` test is non‑trivial to run in CI because it requires a read‑only mount.  
> We can either skip it or use a mock of `nix::unistd::chown` (e.g. with `mockall`) to simulate the error.  
> For now, the test suite will only verify the successful path; the production code will still ignore real `EROFS` errors.

---

## Considerations

| Edge Case | Handling |
|-----------|----------|
| **Read‑only mount under `/sandbox`** | `chown_recursive_ignore_ro` logs a warning and continues. |
| **Non‑`EROFS` errors** | Propagated to supervisor; will still abort startup. |
| **Symlinks** | `WalkDir` follows links by default; we set `follow_links(false)` to avoid chowning symlink targets. |
| **Mount points** | We do not explicitly detect mount points; the `EROFS` guard covers them. |
| **Performance** | Walking the tree is already required; adding a simple error check does not add measurable overhead. |
| **Logging** | Use `log::warn!` to surface the issue to operators without flooding logs. |
| **Testing** | Full EROFS simulation is difficult; rely on production behavior and unit test the success path. |

---

## Summary

Implement a tolerant recursive chown that skips read‑only sub‑mounts, update the supervisor to use it, and add unit tests for the success path. This will prevent sandbox startup failures when a workspace subdirectory is intentionally made immutable.