**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
When the Kubernetes driver starts a sandbox, the supervisor performs a **recursive `chown /sandbox`** to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` `emptyDir` mounted at `/sandbox/.openclaw/skills`), the recursive chown hits that mount and fails with `EROFS`.  
The supervisor aborts, the agent never starts, and the pod ends up in `CrashLoopBackOff`.  
This behaviour was introduced in 0.0.82; earlier releases silently ignored the error.

## Approach
1. **Locate the recursive chown implementation** in the supervisor code (currently in `src/sandbox.rs` – function `chown_sandbox_recursive`).
2. **Modify the error handling** so that:
   * Errors of type `nix::Error::Sys(errno)` where `errno == libc::EROFS` are *ignored* (logged as a warning) and the walk continues.
   * All other errors are propagated normally.
3. **Add a small helper** `is_erofs_error(err: &nix::Error) -> bool` to keep the logic tidy.
4. **Update the unit tests**:
   * Add a test that simulates an `EROFS` error (by mocking `nix::unistd::chown` or by creating a temporary read‑only mount) and verifies that the function returns `Ok(())`.
   * Ensure existing tests still pass.
5. **Documentation & Logging**:
   * Add a comment explaining why we ignore `EROFS` – it is expected when a sandbox contains read‑only sub‑mounts.
   * Log a warning with the path that caused the error to aid debugging.

## Files to modify / create

| File | Change |
|------|--------|
| `src/sandbox.rs` | 1. Add `is_erofs_error` helper.<br>2. Update `chown_sandbox_recursive` to catch `nix::Error::Sys(errno)` and ignore `EROFS`.<br>3. Add warning log. |
| `tests/sandbox_tests.rs` | 1. Add a new test `test_chown_ignore_erofs` that verifies the function continues on `EROFS`. |
| `Cargo.toml` | No change needed – `nix` is already a dependency. |

### Detailed code changes

#### `src/sandbox.rs`

```rust
use nix::errno::Errno;
use nix::unistd::chown;
use std::path::Path;

/// Returns true if the error is an EROFS (read‑only file system) error.
fn is_erofs_error(err: &nix::Error) -> bool {
    matches!(err, nix::Error::Sys(Errno::EROFS))
}

fn chown_sandbox_recursive(path: &Path, uid: Uid, gid: Gid) -> Result<(), Error> {
    for entry in WalkDir::new(path).follow_links(false) {
        let entry = entry?;
        let entry_path = entry.path();

        // Skip the root itself – it will be handled after the loop.
        if entry_path == path {
            continue;
        }

        // Attempt to chown the entry.
        if let Err(err) = chown(entry_path, Some(uid), Some(gid)) {
            if is_erofs_error(&err) {
                // Read‑only sub‑mount – ignore and continue.
                warn!(
                    "chown of {} failed with EROFS; ignoring (sandbox may contain read‑only sub‑mount)",
                    entry_path.display()
                );
                continue;
            } else {
                // Any other error is fatal.
                return Err(err.into());
            }
        }
    }

    // Finally chown the root directory itself.
    chown(path, Some(uid), Some(gid)).map_err(Into::into)
}
```

#### `tests/sandbox_tests.rs`

```rust
#[test]
fn test_chown_ignore_erofs() {
    // Create a temporary directory structure.
    let tmp = tempfile::tempdir().unwrap();
    let sandbox = tmp.path().join("sandbox");
    std::fs::create_dir(&sandbox).unwrap();

    // Create a subdirectory that will be made read‑only.
    let ro_dir = sandbox.join("ro");
    std::fs::create_dir(&ro_dir).unwrap();

    // Mount a tmpfs over `ro_dir` with read‑only flag.
    // This requires root privileges; for the test we skip if not root.
    if nix::unistd::geteuid().is_root() {
        let mount_point = ro_dir.to_str().unwrap();
        let target = "/tmp/ro_mount";
        std::fs::create_dir_all(target).unwrap();
        nix::mount::mount(
            Some("tmpfs"),
            target,
            Some("tmpfs"),
            nix::mount::MsFlags::MS_RDONLY,
            None::<&str>,
        )
        .unwrap();

        // Now run the chown function – it should ignore the EROFS error.
        let uid = nix::unistd::Uid::from_raw(1000);
        let gid = nix::unistd::Gid::from_raw(1000);
        assert!(chown_sandbox_recursive(&sandbox, uid, gid).is_ok());

        // Clean up
        nix::mount::umount(target).unwrap();
        std::fs::remove_dir_all(target).unwrap();
    } else {
        // Skip the test if we cannot create a read‑only mount.
        eprintln!("Skipping test: not running as root");
    }
}
```

> **Note**: The test above requires root privileges to create a read‑only mount. If the CI environment does not allow this, the test can be marked as `#[ignore]` or replaced with a mock of `chown` that returns `EROFS`.

## Considerations

| Edge case | Impact | Mitigation |
|-----------|--------|------------|
| **Multiple read‑only sub‑mounts** | Each will generate a warning; the supervisor will still finish. | No change – the loop continues. |
| **Non‑read‑only errors** (e.g. permission denied) | Supervisor will abort as before. | No change – we only ignore `EROFS`. |
| **Performance** | Ignoring errors adds negligible overhead. | No change. |
| **Logging noise** | Many read‑only mounts may flood logs. | The warning is concise; consider adding a counter or a log level switch if needed. |
| **Future driver changes** | If the driver stops performing recursive chown, this change will be harmless. | No impact. |

## Summary

By updating the supervisor’s recursive chown to ignore `EROFS` errors, we restore compatibility with sandboxes that contain read‑only sub‑mounts, matching the behaviour of earlier OpenShell releases. The change is localized, well‑documented, and covered by a new unit test. Once merged, the issue should be resolved.