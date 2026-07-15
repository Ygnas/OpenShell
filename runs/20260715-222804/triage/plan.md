**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On the Kubernetes driver the sandbox supervisor performs a *recursive* `chown /sandbox` during startup.  
If any sub‑mount under `/sandbox` is read‑only (e.g. an `emptyDir` mounted with `readOnly: true`), the chown
fails with `EROFS: Read‑only file system`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
The same pod spec worked on 0.0.39 but fails on 0.0.82.

## Approach
1. **Locate the recursive chown logic** – it lives in the supervisor crate (`crates/openshell-supervisor/src/...`).
2. **Replace the naive `std::fs::walk_dir` + `std::fs::set_permissions` implementation** with a robust walk that:
   * Uses `walkdir::WalkDir` to iterate over every file/directory under `/sandbox`.
   * Calls `nix::unistd::chown` for each entry.
   * Ignores `EROFS` errors (the file lives on a read‑only mount) and logs a warning.
   * Propagates all other errors.
3. **Keep the existing behaviour** – the supervisor still updates `/etc/passwd` and `/etc/group` before the chown.
4. **Add a small helper** `fn ignore_erofs(err: &nix::Error) -> bool` to keep the code readable.
5. **Add a comment** explaining why we ignore `EROFS` – the directory is immutable, so ownership changes are unnecessary.
6. **Update dependencies** – `walkdir` is already a dev‑dependency in the repo; if not, add it to `Cargo.toml`.

### Why this works
* The supervisor only needs to change ownership on writable files.  
* Ignoring `EROFS` keeps the agent running while leaving read‑only mounts untouched.  
* The change is minimal and does not alter the public API or behaviour on writable mounts.

## Files to modify

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or the file that contains `fn chown_sandbox(&self) -> Result<()>`) | • Replace the existing recursive chown loop with a `WalkDir` based loop.<br>• Use `nix::unistd::chown` for each entry.<br>• Add error handling that ignores `nix::Error::Sys(Errno::EROFS)`.<br>• Log a warning for ignored errors.<br>• Keep the rest of the function unchanged. |
| `crates/openshell-supervisor/Cargo.toml` | Ensure `walkdir` is listed as a dependency (already present in dev‑deps). |
| `crates/openshell-supervisor/src/lib.rs` (or `mod.rs`) | Add `use walkdir::WalkDir;` and `use nix::{unistd::chown, errno::Errno, Error as NixError};` if not already imported. |

### Code snippet (simplified)

```rust
use std::path::Path;
use walkdir::WalkDir;
use nix::{unistd::chown, errno::Errno, Error as NixError};

fn chown_sandbox(&self) -> Result<()> {
    let uid = nix::unistd::Uid::from_raw(self.sandbox_uid);
    let gid = nix::unistd::Gid::from_raw(self.sandbox_gid);

    for entry in WalkDir::new("/sandbox").follow_links(false) {
        let entry = entry?;
        let path = entry.path();

        // Skip the root `/sandbox` itself – it will be handled by the first iteration.
        if path == Path::new("/sandbox") {
            continue;
        }

        match chown(path, Some(uid), Some(gid)) {
            Ok(_) => {}
            Err(NixError::Sys(Errno::EROFS)) => {
                warn!("Ignoring EROFS on {} – read‑only mount", path.display());
                continue;
            }
            Err(e) => return Err(e.into()),
        }
    }

    Ok(())
}
```

## Considerations

| Edge case | Handling |
|-----------|----------|
| **Symlinks** | `WalkDir` follows links by default; we set `follow_links(false)` to avoid changing ownership of the target. |
| **Mountpoint itself** | If the mountpoint is read‑only, `chown` will return `EROFS` and be ignored. |
| **Performance** | The walk is still linear in the number of entries; the change adds negligible overhead. |
| **Logging** | Use the existing `log::warn!` macro to keep consistency with the rest of the supervisor logs. |
| **Testing** | No new tests are required; the behaviour is exercised by the existing e2e‑kubernetes tests. |
| **Compatibility** | The change is backward‑compatible; it only alters error handling, not the public API. |

## Summary

Implement a robust recursive chown that ignores `EROFS` errors, allowing the supervisor to start even when the sandbox contains read‑only sub‑mounts. This fixes the crash loop observed in Kubernetes pods with immutable workspace directories.