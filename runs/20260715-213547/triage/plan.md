**Implementation Plan – Issue #2294**  
*File: `/tmp/plan.md`*

```markdown
# Issue #2294 – Recursive `chown /sandbox` fails on read‑only submounts

## Issue
During sandbox startup the **Kubernetes driver** supervisor performs a
recursive `chown /sandbox` to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true`
`emptyDir` mounted at `/sandbox/.openclaw/skills`), the recursive chown
hits that mount point and aborts with `EROFS`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.

This started after upgrading to **0.0.82**; earlier releases performed
the same operation successfully.

## Approach
Modify the supervisor’s recursive chown routine so that it **skips
entire sub‑trees that are mounted read‑only**.  
The change will:

1. Detect whether a path is on a read‑only mount using `statfs` (via
   the `nix` crate).
2. Use `WalkDir::filter_entry` to prune the walk at any read‑only
   mount point, preventing the chown from ever touching that subtree.
3. Log a warning when a subtree is skipped so that users are aware of
   the omission.
4. Preserve the existing behaviour for all other paths.

This keeps the supervisor logic simple, avoids unnecessary error
handling, and ensures that the sandbox can start even when immutable
sub‑directories are present.

## Files to Modify / Add

| File | Change |
|------|--------|
| `crates/openshell-supervisor/Cargo.toml` | Add `nix = "0.26"` (or latest compatible) and `walkdir = "2.3"` if not already present. |
| `crates/openshell-supervisor/src/sandbox.rs` (or wherever the recursive chown is implemented) |  |
| 1. Add helper `fn is_readonly_mount(path: &Path) -> bool` that calls `nix::mount::statfs` and checks `MS_RDONLY`. |
| 2. Replace the current `WalkDir::new("/sandbox")` loop with one that uses `filter_entry(|e| !is_readonly_mount(e.path()))`. |
| 3. Keep the existing `chown` logic (using `nix::unistd::chown`) but wrap it in a `match` that logs a warning on `Err(Errno::EROFS)` and continues. |
| 4. Add unit tests in `tests/sandbox_chown.rs` that: |
|    - Create a temporary directory structure with a read‑only sub‑mount (using `mount --bind` + `mount -o remount,ro`). |
|    - Run the chown routine and assert that the read‑only subtree was skipped and that other files were chowned. |
| 5. Update any documentation or comments that mention the recursive chown. |

### Detailed Code Changes

```rust
// crates/openshell-supervisor/src/sandbox.rs

use std::path::Path;
use nix::mount::statfs;
use nix::sys::stat::Mode;
use nix::unistd::{chown, Gid, Uid};
use walkdir::WalkDir;
use log::{info, warn};

/// Returns true if `path` is on a read‑only mount.
fn is_readonly_mount(path: &Path) -> bool {
    match statfs(path) {
        Ok(fs) => fs.flags() & libc::MS_RDONLY != 0,
        Err(_) => false, // If we can't stat, assume writable to avoid skipping.
    }
}

/// Recursively chown `/sandbox`, skipping read‑only sub‑mounts.
pub fn chown_sandbox_recursive(uid: Uid, gid: Gid) -> Result<(), std::io::Error> {
    let sandbox_root = Path::new("/sandbox");
    for entry in WalkDir::new(sandbox_root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| !is_readonly_mount(e.path()))
    {
        let entry = entry?;
        let path = entry.path();
        // Skip the mount point itself if it is read‑only – the filter already
        // handles this, but we keep the guard for safety.
        if is_readonly_mount(path) {
            warn!("Skipping read‑only mount during chown: {:?}", path);
            continue;
        }

        // Perform the chown; ignore EROFS errors (should not happen due to filter).
        match chown(path, Some(uid), Some(gid)) {
            Ok(_) => {}
            Err(nix::Error::Sys(nix::errno::Errno::EROFS)) => {
                warn!("EROFS while chowning {:?} – skipping", path);
            }
            Err(e) => return Err(std::io::Error::new(std::io::ErrorKind::Other, e)),
        }
    }
    Ok(())
}
```

### Tests

```rust
// tests/sandbox_chown.rs

#[test]
fn test_chown_skips_readonly_submount() {
    // 1. Create temp sandbox root
    // 2. Create subdir /sandbox/.openclaw/skills
    // 3. Bind mount it to a temp dir and remount read‑only
    // 4. Run chown_sandbox_recursive
    // 5. Assert that files in the read‑only subtree retain original ownership
    //    and that other files were chowned.
}
```

## Considerations

| Edge Case | Mitigation |
|-----------|------------|
| **Mount point cannot be statfs‑ed** | `is_readonly_mount` returns `false` on error, so the path will be processed. If the mount is actually read‑only but we cannot detect it, the chown may fail with `EROFS`. The error is logged and the process continues. |
| **Multiple nested read‑only mounts** | `filter_entry` prunes the entire subtree at the first read‑only mount, so nested read‑only mounts are also skipped. |
| **Performance** | The additional `statfs` call per directory is negligible compared to the chown operation. |
| **Compatibility** | The change only affects the supervisor; the driver and runtime remain unchanged. |
| **Logging** | A warning is emitted for each skipped subtree to aid debugging. |
| **Testing** | The unit test uses `mount` commands; it will only run on Linux hosts with sufficient privileges. |

## Summary

Implement the above changes to make the supervisor resilient to read‑only
sub‑mounts under `/sandbox`.  This will prevent the `EROFS` crash and
allow pods that mount immutable directories to start successfully.
```

This plan should be written to `/tmp/plan.md`.