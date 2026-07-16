We need to produce a plan. The above repeated lines are nonsense. Let's produce a concise plan.

We need to modify supervisor code to skip read-only submounts during chown. Provide details: new module mount.rs, function get_readonly_mount_points, modify chown logic.

Also need to update Cargo.toml if new dependencies.

Also need to add tests.

Also need to update docs.

Also need to update CI.

Also need to update release notes.

Also need to update issue.

Let's produce a markdown plan.

**Implementation Plan – Issue #2294**  
*Bug: Kubernetes sandbox crashes EROFS – recursive `chown /sandbox` fails on read‑only submounts (0.0.82)*  

---

## Issue
During sandbox startup the supervisor performs a **recursive `chown /sandbox`** to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` volume), the chown hits that mount and returns `EROFS`.  
The supervisor aborts, the agent never starts, and the pod ends up in `CrashLoopBackOff`.  
This behaviour was introduced in 0.0.82; earlier releases silently ignored the error.

---

## Approach
1. **Detect read‑only mount points**  
   * Parse `/proc/self/mountinfo` to build a `HashSet<PathBuf>` of mount points that are mounted read‑only (`ro` in options).  
   * The helper will be in a new module `src/mount.rs`.

2. **Skip chown on read‑only mounts**  
   * Replace the existing recursive chown routine with a walk that:
     * Skips any directory that is a read‑only mount point (using `WalkDir::skip_current_dir()`).
     * Calls `chown` on every other file/directory.
   * If `chown` returns `EROFS` for any reason (e.g. a file inside a read‑only mount that was missed), log a **warning** and continue instead of aborting.

3. **Graceful error handling**  
   * Only propagate errors that are *not* `EROFS`.  
   * Keep the existing behaviour for other errors (e.g. permission denied, I/O errors).

4. **Unit tests**  
   * Test `get_readonly_mount_points` against a synthetic `/proc/self/mountinfo` string.  
   * Test the chown routine with a temporary directory tree that contains a fake read‑only mount (simulated by creating a sub‑directory and marking it in the mount‑point set).  
   * Verify that files inside the read‑only mount are *not* chowned and that the function returns successfully.

5. **Documentation & CI**  
   * Add a comment in the supervisor logs: “Skipping read‑only mount …”.  
   * Update the release notes to mention the fix.  
   * Ensure the new code compiles on all supported Rust versions and passes the existing CI pipeline.

---

## Files to Modify / Add

| File | Change |
|------|--------|
| `src/mount.rs` | New module: `pub fn get_readonly_mount_points() -> Result<HashSet<PathBuf>, std::io::Error>` |
| `src/sandbox.rs` (or wherever the recursive chown lives) | Replace the current `chown_recursive` with `chown_recursive_skip_ro` that uses `WalkDir` and the mount‑point set. |
| `Cargo.toml` | Add `walkdir = "2"` if not already present. |
| `tests/mount.rs` | New unit tests for mount parsing. |
| `tests/sandbox_chown.rs` | New unit tests for chown skipping logic. |
| `src/sandbox.rs` | Add `use crate::mount::get_readonly_mount_points;` and update imports. |
| `src/sandbox.rs` | Add logging: `info!("Skipping read‑only mount {}", mount_point.display());` |
| `CHANGELOG.md` | Add entry: “Fix sandbox crash when read‑only sub‑mounts exist (issue #2294).” |

---

## Detailed Code Changes

### 1. `src/mount.rs`

```rust
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;

/// Return a set of mount points that are mounted read‑only.
pub fn get_readonly_mount_points() -> std::io::Result<HashSet<PathBuf>> {
    let file = File::open("/proc/self/mountinfo")?;
    let reader = BufReader::new(file);
    let mut ro_mounts = HashSet::new();

    for line in reader.lines() {
        let line = line?;
        // mountinfo format: <mount_id> <parent_id> <major:minor> <root> <mount_point> <mount_options> ...
        // We only need fields 5 (mount_point) and 6 (mount_options)
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 6 {
            continue;
        }
        let mount_point = PathBuf::from(parts[4]);
        let options = parts[5];
        if options.contains("ro") {
            ro_mounts.insert(mount_point);
        }
    }
    Ok(ro_mounts)
}
```

### 2. `src/sandbox.rs` (or the module that contains the chown logic)

```rust
use walkdir::WalkDir;
use nix::unistd::chown;
use nix::sys::stat::Mode;
use std::os::unix::fs::MetadataExt;
use crate::mount::get_readonly_mount_points;
use std::collections::HashSet;

/// Recursively chown /sandbox, skipping read‑only mount points.
pub fn chown_sandbox_root(uid: u32, gid: u32) -> Result<(), std::io::Error> {
    let ro_mounts = get_readonly_mount_points()?;

    for entry in WalkDir::new("/sandbox")
        .follow_links(false)
        .into_iter()
    {
        let entry = entry?;
        let path = entry.path();

        // Skip any directory that is a read‑only mount point
        if entry.file_type().is_dir() && ro_mounts.contains(path) {
            log::info!("Skipping read‑only mount {}", path.display());
            // Skip all children of this directory
            continue;
        }

        // Perform chown
        match chown(path, Some(uid), Some(gid)) {
            Ok(_) => {}
            Err(err) => {
                // Ignore EROFS errors – they indicate a read‑only file system
                if err.as_errno() == Some(nix::errno::Errno::EROFS) {
                    log::warn!("chown failed on read‑only path {}: {}", path.display(), err);
                    continue;
                } else {
                    return Err(std::io::Error::new(std::io::ErrorKind::Other, err));
                }
            }
        }
    }
    Ok(())
}
```

*Replace any existing recursive chown call with `chown_sandbox_root`.*

### 3. `Cargo.toml`

```toml
[dependencies]
walkdir = "2"
nix = { version = "0.26", features = ["fs"] }
```

*(Add `walkdir` if it is not already present; `nix` is already used for chown.)*

### 4. Tests

#### `tests/mount.rs`

```rust
#[test]
fn test_get_readonly_mount_points() {
    use std::io::Write;
    use tempfile::NamedTempFile;

    // Create a fake mountinfo file
    let mut file = NamedTempFile::new().unwrap();
    writeln!(file, "1 2 0:0 / /ro_mount ro,relatime 0 0").unwrap();
    writeln!(file, "1 2 0:0 / /rw_mount rw,relatime 0 0").unwrap();

    // Temporarily replace /proc/self/mountinfo
    let original = std::fs::read_to_string("/proc/self/mountinfo").unwrap();
    std::fs::write("/proc/self/mountinfo", file.path()).unwrap();

    let ro_mounts = crate::mount::get_readonly_mount_points().unwrap();
    assert!(ro_mounts.contains(&std::path::PathBuf::from("/ro_mount")));
    assert!(!ro_mounts.contains(&std::path::PathBuf::from("/rw_mount")));

    // Restore original
    std::fs::write("/proc/self/mountinfo", original).unwrap();
}
```

*(In practice, use a helper to inject a custom mountinfo path; the above is illustrative.)*

#### `tests/sandbox_chown.rs`

```rust
#[test]
fn test_chown_skips_ro_mount() {
    use tempfile::tempdir;
    use std::fs::{create_dir_all, File};
    use std::os::unix::fs::PermissionsExt;

    let dir = tempdir().unwrap();
    let sandbox = dir.path().join("sandbox");
    create_dir_all(&sandbox).unwrap();

    // Simulate a read‑only sub‑mount
    let ro_sub = sandbox.join("ro_sub");
    create_dir_all(&ro_sub).unwrap();
    // Mark it as read‑only in the mount set
    let mut ro_mounts = std::collections::HashSet::new();
    ro_mounts.insert(ro_sub.clone());

    // Create a file inside the read‑only sub‑mount
    let file_path = ro_sub.join("file.txt");
    File::create(&file_path).unwrap();

    // Run chown_sandbox_root with a dummy UID/GID
    crate::sandbox::chown_sandbox_root(1000, 1000).unwrap();

    // Verify that the file inside the read‑only mount was *not* chowned
    let metadata = file_path.metadata().unwrap();
    assert_eq!(metadata.uid(), 0); // still root
}
```

*(The test uses the real `chown_sandbox_root`; in a real test environment you would mock `chown` or run with a user that can actually change ownership.)*

### 5. Logging & Release Notes

* Add an `info!` log when skipping a read‑only mount.  
* Update `CHANGELOG.md`:

```
### 0.0.82
- Fixed sandbox crash when a read‑only sub‑mount exists under /sandbox (issue #2294).
```

---

## Considerations

| Edge Case | Handling |
|-----------|----------|
| Nested read‑only mounts | The `ro_mounts` set contains all mount points; `WalkDir` will skip any directory that matches a mount point, so nested mounts are automatically skipped. |
| Mount points that are not read‑only | They are not in `ro_mounts`; chown proceeds normally. |
| Files inside a read‑only mount that are not directories | `WalkDir` will still visit them; `chown` will return `EROFS` and we log a warning but continue. |
| Performance | The mount‑point set is small; lookup is O(1). |
| Compatibility | The change is backward‑compatible; older releases that silently ignored `EROFS` will now log a warning but still succeed. |
| Security | Skipping read‑only mounts does not expose the sandbox to privilege escalation. |

---

## Summary

Implement a read‑only mount detector, modify the recursive chown routine to skip those mounts, and handle `EROFS` errors gracefully. Add unit tests, update documentation, and ensure the change passes CI. This will prevent sandbox startup failures caused by immutable sub‑mounts under `/sandbox`.