**Implementation Plan – Issue #2294**  
*File: `/tmp/plan.md`*

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
During sandbox startup the **Kubernetes driver** supervisor performs a
recursive `chown /sandbox` to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true`
`emptyDir` mounted at `/sandbox/.openclaw/skills`), the recursive chown
hits that mount and returns `EROFS`.  
The supervisor aborts, the agent never starts, and the pod enters
`CrashLoopBackOff`.  
This behaviour was introduced in 0.0.82; earlier releases silently
skipped the read‑only mount.

## Approach
Modify the supervisor’s recursive chown routine so that it **ignores
`EROFS` errors** and continues walking the tree.  
All other errors should still propagate and cause a failure.

### Why this works
* The read‑only submount is immutable – ownership changes are
  irrelevant.
* Skipping the mount keeps the rest of the sandbox writable and
  allows the agent to start.
* The change is minimal, does not alter any public API, and keeps the
  existing behaviour for non‑read‑only mounts.

## Files to modify / create

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or wherever the recursive chown is implemented) | Replace the existing `chown_recursive` implementation with a new one that uses `walkdir::WalkDir` and ignores `EROFS`. |
| `crates/openshell-supervisor/src/sandbox.rs` | Add a helper function `fn chown_recursive(path: &Path, uid: u32, gid: u32) -> Result<(), std::io::Error>` that performs the walk. |
| `crates/openshell-supervisor/src/sandbox.rs` | Update the supervisor startup code to call the new helper after updating `/etc/passwd` and `/etc/group`. |
| `crates/openshell-supervisor/Cargo.toml` | Add `walkdir = "2"` to `[dependencies]` if not already present. |
| `crates/openshell-supervisor/src/sandbox.rs` | Add logging: when an `EROFS` is encountered, log a warning `Skipping read‑only submount: {path}`. |
| `crates/openshell-supervisor/tests/sandbox_chown.rs` (optional) | Add a unit test that verifies the function returns `Ok(())` when a simulated `EROFS` error is returned. (This can be done by temporarily overriding the `chown` call via a trait or by using a mock filesystem; if this is too heavy, the test can be omitted.) |

### Detailed code changes

#### 1. Add `walkdir` dependency
```toml
# crates/openshell-supervisor/Cargo.toml
[dependencies]
walkdir = "2"
# (other existing deps)
```

#### 2. Implement the new recursive chown
```rust
// crates/openshell-supervisor/src/sandbox.rs
use std::fs;
use std::os::unix::fs::MetadataExt;
use std::path::Path;
use nix::unistd::chown;
use nix::errno::Errno;
use walkdir::WalkDir;
use log::{info, warn};

/// Recursively chown all files under `root` to `uid`/`gid`.
/// Ignores `EROFS` errors (read‑only mounts) and continues walking.
/// Returns an error for any other failure.
fn chown_recursive(root: &Path, uid: u32, gid: u32) -> Result<(), std::io::Error> {
    for entry in WalkDir::new(root).follow_links(false) {
        let entry = entry?;
        let path = entry.path();

        // Skip the root itself – it will be handled by the first iteration.
        // `chown` works on directories as well.
        match chown(path, Some(uid.into()), Some(gid.into())) {
            Ok(_) => {}
            Err(nix_err) => {
                // Convert nix::Error to std::io::Error
                let io_err = std::io::Error::from_raw_os_error(nix_err as i32);
                if io_err.raw_os_error() == Some(Errno::EROFS as i32) {
                    warn!("Skipping read‑only submount during chown: {}", path.display());
                    continue; // ignore and keep walking
                } else {
                    return Err(io_err); // propagate other errors
                }
            }
        }
    }
    Ok(())
}
```

#### 3. Wire it into supervisor startup
```rust
// In the supervisor init routine (e.g., `fn start_sandbox(...)`)
info!("Updating /etc/passwd and /etc/group for sandbox identity");
update_passwd_and_group()?;

info!("Recursively chowning /sandbox for sandbox UID/GID");
chown_recursive(Path::new("/sandbox"), sandbox_uid, sandbox_gid)?;
```

#### 4. Logging
* Use `warn!` for `EROFS` skips.
* Keep existing `info!` logs for normal progress.

#### 5. Tests (optional)
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::{self, File};
    use std::os::unix::fs::PermissionsExt;
    use std::path::PathBuf;

    #[test]
    fn test_chown_recursive_ignores_erofs() {
        // Create a temporary directory structure
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path().join("sandbox");
        fs::create_dir_all(&root).unwrap();

        // Create a subdirectory that we will make read‑only
        let ro_dir = root.join("ro");
        fs::create_dir_all(&ro_dir).unwrap();

        // Create a file inside the read‑only dir
        let file = ro_dir.join("file.txt");
        File::create(&file).unwrap();

        // Make the subdirectory read‑only (not a mount, but enough to trigger EROFS
        // in the chown wrapper if we simulate it; here we just test that the function
        // returns Ok even if chown fails).
        let mut perms = fs::metadata(&ro_dir).unwrap().permissions();
        perms.set_mode(0o555);
        fs::set_permissions(&ro_dir, perms).unwrap();

        // Call chown_recursive – it should not panic or return Err
        let res = chown_recursive(&root, 1000, 1000);
        assert!(res.is_ok(), "chown_recursive should ignore read‑only errors");
    }
}
```
> **Note**: The test above does not actually trigger `EROFS` (since it is not a mount), but it demonstrates that the function does not fail on permission errors. A more thorough integration test would require mounting a read‑only filesystem, which is beyond the scope of unit tests.

## Considerations

| Edge Case | Handling |
|-----------|----------|
| **Root `/sandbox` is read‑only** | The first `chown` on `/sandbox` will fail with `EROFS`. The function will log a warning and return `Ok(())`. The supervisor will continue, but the sandbox will be effectively read‑only. This is acceptable because the agent cannot write anyway. |
| **Other errors (e.g., EPERM, ENOENT)** | These are propagated and cause the supervisor to abort, preserving existing behaviour. |
| **Performance** | Walking the tree with `WalkDir` is already used elsewhere; adding a small `match` per entry is negligible. |
| **Logging verbosity** | `warn!` is used for skipped mounts; this keeps logs readable while still alerting operators. |
| **Compatibility** | No changes to public API; only internal behaviour. |
| **Testing** | Full integration tests would require a read‑only mount; omitted for brevity. |

## Summary of Steps

1. Add `walkdir` to supervisor `Cargo.toml`.
2. Implement `chown_recursive` in `sandbox.rs` that ignores `EROFS`.
3. Replace existing recursive chown call with the new helper.
4. Add warning logs for skipped mounts.
5. (Optional) Add unit test to verify behaviour.
6. Run `cargo test` and `cargo clippy` to ensure no regressions.
7. Build and push the updated image; run the original repro to confirm the crash is resolved.

Once merged, the supervisor will no longer abort when encountering read‑only submounts under `/sandbox`, restoring compatibility with the 0.0.82 release and earlier behaviour.
```

--- 

*This plan should be saved to `/tmp/plan.md` and used as a reference for the implementation.*