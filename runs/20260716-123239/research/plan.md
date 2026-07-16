**Implementation Plan – Issue #2294**  
*Bug: Kubernetes sandbox crashes EROFS – recursive `chown /sandbox` fails on read‑only submounts (0.0.82)*  

---

## Issue
During sandbox startup the **Kubernetes driver** injects `OPENSHELL_SANDBOX_UID`/`GID` and the supervisor performs a **recursive `chown /sandbox`**.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` volume), the recursive chown hits that mount and aborts with `EROFS`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
The failure surfaced in 0.0.82; earlier releases silently ignored the error.

---

## Approach
1. **Detect read‑only mounts**  
   * Parse `/proc/self/mountinfo` to build a map of mount points → mount options.  
   * For any path, find the longest matching mount point and check if the `ro` flag is present.

2. **Skip chown on read‑only mounts**  
   * In the recursive chown routine, before recursing into a directory, call `is_readonly_mount`.  
   * If the directory is a read‑only mount, skip the entire subtree.  
   * For files inside a read‑only mount, ignore `EROFS` errors; propagate all other errors.

3. **Graceful error handling**  
   * If a chown on a file/directory fails with `EROFS`, treat it as a non‑fatal error and continue.  
   * Any other error should still abort the supervisor startup.

4. **Unit / Integration test** (optional)  
   * A test that mounts a read‑only bind mount under `/sandbox` and verifies that the supervisor does **not** crash.  
   * (If mounting is not feasible in CI, skip the test but document the intended behaviour.)

---

## Files & Changes

| File | Change | Rationale |
|------|--------|-----------|
| `crates/openshell-supervisor/src/sandbox.rs` (or wherever `chown_sandbox_root` lives) | 1. Add helper `is_readonly_mount(path: &Path) -> Result<bool>` that parses `/proc/self/mountinfo`. 2. Modify the recursive chown routine to: <br>• Skip directories that are read‑only mounts. <br>• Ignore `EROFS` errors on files. | Centralises mount‑check logic and prevents chown on read‑only sub‑mounts. |
| `crates/openshell-supervisor/src/sandbox.rs` | Update documentation comments to explain new behaviour. | Keeps code self‑documenting. |
| `Cargo.toml` (supervisor crate) | No new dependencies – uses `std` and `nix` already present. | N/A |
| `tests/sandbox_chown.rs` (optional) | Add integration test that mounts a read‑only bind mount under `/sandbox` and asserts supervisor starts. | Validates behaviour. |

### Detailed Code Changes

#### 1. Helper: `is_readonly_mount`

```rust
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};

/// Returns `Ok(true)` if *path* is inside a read‑only mount point.
/// The function parses `/proc/self/mountinfo` once per call; for
/// performance you could cache the result, but the call is cheap
/// and the function is only used during sandbox startup.
fn is_readonly_mount(path: &Path) -> std::io::Result<bool> {
    let canonical = path.canonicalize()?;
    let file = File::open("/proc/self/mountinfo")?;
    let reader = BufReader::new(file);

    // Find the longest matching mount point.
    let mut best_match: Option<(PathBuf, String)> = None;
    for line in reader.lines() {
        let line = line?;
        // mountinfo format: <mount_id> <parent_id> <major:minor> <root> <mount_point> <options> ...
        let mut parts = line.split_whitespace();
        let _mount_id = parts.next();
        let _parent_id = parts.next();
        let _major_minor = parts.next();
        let _root = parts.next();
        let mount_point = parts.next().unwrap_or("");
        let options = parts.next().unwrap_or("");

        let mp = Path::new(mount_point);
        if canonical.starts_with(mp) {
            if best_match.is_none() || mp.as_os_str().len() > best_match.as_ref().unwrap().0.as_os_str().len() {
                best_match = Some((mp.to_path_buf(), options.to_string()));
            }
        }
    }

    if let Some((_mp, opts)) = best_match {
        Ok(opts.split(',').any(|o| o == "ro"))
    } else {
        Ok(false)
    }
}
```

#### 2. Recursive chown

```rust
use nix::unistd::{chown, Gid, Uid};
use nix::errno::Errno;

fn chown_sandbox_root(root: &Path, uid: Uid, gid: Gid) -> Result<(), std::io::Error> {
    // First chown the root itself
    chown(root, Some(uid), Some(gid)).map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    for entry in std::fs::read_dir(root)? {
        let entry = entry?;
        let path = entry.path();

        // Skip if this is a read‑only mount point
        if is_readonly_mount(&path).unwrap_or(false) {
            log::debug!("Skipping read‑only mount subtree: {:?}", path);
            continue;
        }

        if path.is_dir() {
            // Recurse
            chown_sandbox_root(&path, uid, gid)?;
        } else {
            // File – ignore EROFS
            match chown(&path, Some(uid), Some(gid)) {
                Ok(_) => {}
                Err(e) => {
                    if e.as_errno() == Some(Errno::EROFS) {
                        log::debug!("Ignoring EROFS on file {:?} during chown", path);
                        continue;
                    } else {
                        return Err(std::io::Error::new(std::io::ErrorKind::Other, e));
                    }
                }
            }
        }
    }
    Ok(())
}
```

#### 3. Call Site

Replace the existing recursive chown call in the supervisor startup logic with the new `chown_sandbox_root` function. Ensure that the UID/GID values are passed correctly (they come from the injected environment variables).

#### 4. Logging

Add debug logs for skipped read‑only mounts and ignored `EROFS` errors to aid troubleshooting.

---

## Considerations

| Edge Case | Handling |
|-----------|----------|
| **Root `/sandbox` is read‑only** | The initial chown on the root will fail; we propagate the error – this is a true failure. |
| **Multiple nested read‑only mounts** | The longest‑matching mount point logic ensures the deepest read‑only mount is detected; the entire subtree is skipped. |
| **Symlinks** | `canonicalize` resolves symlinks; if a symlink points into a read‑only mount, it will be skipped. |
| **Performance** | Parsing `/proc/self/mountinfo` is O(n) per call; called only once per directory entry. Caching could be added if profiling shows a bottleneck. |
| **Testing** | Mounting a read‑only bind mount in CI may require privileged containers; if not feasible, document the intended behaviour and rely on manual testing. |
| **Compatibility** | The change is backward‑compatible; older releases that silently ignored `EROFS` will now behave the same. |

---

## Summary

Implement a read‑only mount detector, modify the recursive chown routine to skip such mounts, and ignore `EROFS` errors on files. This will prevent the supervisor from crashing when a sandbox contains read‑only sub‑mounts, restoring the behaviour seen in earlier OpenShell releases.