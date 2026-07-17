**Implementation Plan – Issue #2294**  
*File: `/tmp/plan.md`*

```markdown
# Issue #2294 – Recursive `chown /sandbox` fails on read‑only submounts

## Issue
During sandbox startup the OpenShell supervisor performs a **recursive `chown /sandbox`** to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` volume in a Kubernetes pod), the recursive chown hits that mount and aborts with `EROFS: Read‑only file system`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
This started after upgrading to **0.0.82**; earlier releases silently ignored the error.

## Approach
1. **Detect read‑only mounts**  
   * Parse `/proc/self/mountinfo` to find the mount point that covers a given path.  
   * Inspect the mount options for the keyword `ro`.  
   * Expose a helper `is_read_only(path: &Path) -> Result<bool, std::io::Error>`.

2. **Modify the recursive chown logic**  
   * Before attempting to `chown` a file/directory, call `is_read_only`.  
   * If the path is on a read‑only mount, skip the chown and log a warning.  
   * If `chown` returns `EROFS`, treat it the same as a read‑only mount: log a warning and continue.  
   * All other errors should still abort the supervisor.

3. **Add tests**  
   * Unit tests for `is_read_only` using a hard‑coded sample of `/proc/self/mountinfo`.  
   * Verify that the helper correctly identifies read‑only vs. read‑write mounts, handles longest‑prefix matching, and returns `false` when no mount matches.  
   * (Optional) Add a small integration test that creates a temporary read‑only bind mount and ensures the supervisor skips it – this requires a privileged test environment and can be skipped if not feasible.

4. **Logging**  
   * Use `log::warn!` to emit a message when a path is skipped due to being read‑only.  
   * Keep the existing `log::error!` for unexpected failures.

5. **Documentation & CI**  
   * Update the supervisor README to note that read‑only submounts are now supported.  
   * Ensure all tests pass on the current CI pipeline.

## Files to Modify / Add
| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/utils/mount.rs` | New module implementing `is_read_only` and helper parsing logic. |
| `crates/openshell-supervisor/src/sandbox.rs` (or wherever recursive chown is implemented) | Wrap chown calls with `is_read_only` check; handle `EROFS` errors gracefully. |
| `crates/openshell-supervisor/src/sandbox.rs` | Add `use crate::utils::mount::is_read_only;` and necessary imports (`std::os::unix::fs::MetadataExt`, `nix::unistd::chown`, `nix::errno::Errno`). |
| `crates/openshell-supervisor/tests/mount.rs` | New test module for `is_read_only`. |
| `Cargo.toml` (supervisor crate) | No new dependencies; ensure `walkdir` and `nix` are already listed. |
| `README.md` (optional) | Add note about read‑only submount support. |

### `mount.rs` – Example Implementation
```rust
use std::fs::read_to_string;
use std::io;
use std::path::{Path, PathBuf};

/// Return `true` if `path` is located on a read‑only mount.
pub fn is_read_only(path: &Path) -> io::Result<bool> {
    let mountinfo = read_to_string("/proc/self/mountinfo")?;
    let mut best_match: Option<(PathBuf, bool)> = None;

    for line in mountinfo.lines() {
        // mountinfo format: <id> <parent> <major:minor> <root> <mount_point> <options> ...
        let mut parts = line.split_whitespace();
        let _id = parts.next();
        let _parent = parts.next();
        let _majmin = parts.next();
        let _root = parts.next();
        let mount_point = parts.next().ok_or_else(|| io::Error::new(io::ErrorKind::Other, "malformed mountinfo"))?;
        let options = parts.next().ok_or_else(|| io::Error::new(io::ErrorKind::Other, "malformed mountinfo"))?;

        let mp_path = Path::new(mount_point);
        if path.starts_with(mp_path) {
            // longest prefix wins
            if best_match.as_ref().map_or(true, |(best, _)| mp_path.as_os_str().len() > best.as_os_str().len()) {
                let ro = options.split(',').any(|opt| opt == "ro");
                best_match = Some((mp_path.to_path_buf(), ro));
            }
        }
    }

    Ok(best_match.map_or(false, |(_, ro)| ro))
}
```

### `sandbox.rs` – Updated Chown Loop
```rust
use crate::utils::mount::is_read_only;
use nix::errno::Errno;
use nix::unistd::chown;
use std::os::unix::fs::MetadataExt;
use walkdir::WalkDir;

fn chown_sandbox_root(root: &Path, uid: Uid, gid: Gid) -> Result<()> {
    for entry in WalkDir::new(root).follow_links(false) {
        let entry = entry?;
        let path = entry.path();

        // Skip read‑only mounts
        if is_read_only(path)? {
            log::warn!("Skipping chown of read‑only path {}", path.display());
            continue;
        }

        let metadata = entry.metadata()?;
        let current_uid = metadata.uid();
        let current_gid = metadata.gid();

        if current_uid != uid || current_gid != gid {
            match chown(path, Some(uid), Some(gid)) {
                Ok(_) => {}
                Err(nix::Error::Sys(Errno::EROFS)) => {
                    log::warn!("Skipping chown of read‑only path {}", path.display());
                }
                Err(e) => return Err(e.into()),
            }
        }
    }
    Ok(())
}
```

## Considerations
- **Mountinfo parsing**: The helper assumes the standard `/proc/self/mountinfo` format. It uses the longest‑prefix rule to determine the correct mount point.  
- **Performance**: The helper reads `/proc/self/mountinfo` on every chown call. Since the chown loop runs only once at startup, this overhead is negligible.  
- **Error handling**: Only `EROFS` is ignored; all other errors (e.g., permission denied) still abort the supervisor.  
- **Testing**: The unit tests cover the parsing logic. Integration tests that actually create read‑only bind mounts are optional and may require privileged test environments.  
- **Compatibility**: The change is backward‑compatible; older images will still chown normally.  
- **Logging**: Warnings are emitted for skipped paths to aid debugging.  

## Next Steps
1. Add `mount.rs` and the helper function.  
2. Update the chown logic in the supervisor.  
3. Add unit tests for `is_read_only`.  
4. Run `cargo test` and ensure all tests pass.  
5. Build the supervisor image and run the Kubernetes sandbox test to confirm the crash is resolved.  
6. Commit, push, and create a PR for review.  

--- 

*End of plan* 
```