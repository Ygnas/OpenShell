**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On Kubernetes driver sandboxes the supervisor performs a recursive `chown /sandbox` during startup to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` `emptyDir` mounted at `/sandbox/.openclaw/skills`), the recursive chown hits that mount point and fails with `EROFS`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
The problem surfaced after upgrading to OpenShell 0.0.82; it worked on 0.0.39.

## Approach
Replace the single `chown /sandbox` call with a robust walk‑and‑chown routine that:

1. Recursively iterates over every file/directory under `/sandbox` (excluding symlinks).
2. Calls `nix::unistd::chown` on each entry.
3. Ignores `Errno::EROFS` errors (read‑only mounts) but propagates all other errors.
4. Logs a warning when an `EROFS` is encountered so that the failure is visible but not fatal.

This keeps the existing behaviour for writable paths while gracefully handling read‑only submounts.

### Why this works
* The supervisor runs as root inside the sandbox, so it can chown any writable file.
* Read‑only mounts are intentionally immutable; changing ownership on them is impossible and should not abort the sandbox.
* Ignoring `EROFS` keeps the logic simple and avoids the need to parse `/proc/mounts` or maintain a list of read‑only subtrees.

## Files to modify / create

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/chown.rs` (new) | Add a helper `fn chown_recursive_skip_ro(path: &Path, uid: Uid, gid: Gid) -> Result<()>` that implements the walk‑and‑chown logic described above. |
| `crates/openshell-supervisor/src/lib.rs` | Re‑export the new helper so it can be used by the supervisor entry point. |
| `crates/openshell-supervisor/src/main.rs` (or the module that performs the chown) | Replace the existing `chown /sandbox` call with `chown_recursive_skip_ro(Path::new("/sandbox"), uid, gid)` and handle the returned `Result`. |
| `crates/openshell-supervisor/Cargo.toml` | Add `walkdir = "2"` to `[dependencies]`. |
| `crates/openshell-supervisor/tests/chown.rs` (new) | Add a unit test that mounts a temporary read‑only directory under a sandbox root and verifies that `chown_recursive_skip_ro` does not return an error. |
| `crates/openshell-supervisor/tests/integration.rs` (existing) | Update any tests that expect a hard failure on read‑only mounts to pass. |
| `crates/openshell-supervisor/src/chown.rs` | Add documentation comments and error handling. |

### Implementation details

```rust
// crates/openshell-supervisor/src/chown.rs
use std::path::Path;
use nix::unistd::{chown, Uid, Gid};
use nix::errno::Errno;
use walkdir::WalkDir;
use anyhow::{Context, Result};

/// Recursively chown `path` and all its descendants, skipping read‑only mounts.
/// `EROFS` errors are ignored; all other errors are returned.
pub fn chown_recursive_skip_ro(path: &Path, uid: Uid, gid: Gid) -> Result<()> {
    for entry in WalkDir::new(path).follow_links(false).into_iter() {
        let entry = entry?;
        let p = entry.path();

        // Skip symlinks – chowning a symlink would affect the target.
        if entry.file_type().is_symlink() {
            continue;
        }

        match chown(p, Some(uid), Some(gid)) {
            Ok(_) => {}
            Err(nix::Error::Sys(Errno::EROFS)) => {
                // Read‑only mount – ignore.
                log::warn!("Skipping chown on read‑only path: {}", p.display());
            }
            Err(e) => return Err(e).context(format!("chown failed on {}", p.display())),
        }
    }
    Ok(())
}
```

*The supervisor entry point* (`src/main.rs` or the module that performs the chown) will now call:

```rust
use openshell_supervisor::chown::chown_recursive_skip_ro;

let sandbox_root = Path::new("/sandbox");
chown_recursive_skip_ro(sandbox_root, sandbox_uid, sandbox_gid)
    .context("Failed to chown sandbox root")?;
```

*Logging*: The helper logs a warning for each `EROFS` it encounters. This keeps the user informed without aborting.

## Considerations

| Edge case | Handling |
|-----------|----------|
| **Multiple read‑only submounts** | Each will generate a warning; the function continues. |
| **Symlinks** | Skipped to avoid affecting the target. |
| **Non‑read‑only permission errors** | Propagated as errors; the sandbox will still fail if it cannot change ownership of a writable file. |
| **Performance** | Walking the entire sandbox tree is already required for the original `chown -R`. The added error handling is negligible. |
| **Testing** | The new unit test mounts a temporary directory with `mount --bind --read-only`. It verifies that `chown_recursive_skip_ro` returns `Ok(())`. |
| **Compatibility** | The change is backward compatible; older versions of the supervisor will still perform a single `chown /sandbox` if the helper is not used. |
| **RuntimeClass** | The change is driver‑agnostic; it will also benefit other drivers that perform a recursive chown. |

## Summary of steps

1. Add `walkdir` to `Cargo.toml`.
2. Create `src/chown.rs` with the recursive chown helper.
3. Re‑export the helper in `lib.rs`.
4. Replace the existing `chown /sandbox` call with the helper.
5. Add unit and integration tests.
6. Run the full test suite and e2e tests on a Kubernetes sandbox with a read‑only submount to confirm the crash is resolved.

Once merged, the supervisor will no longer abort on read‑only submounts, restoring the behaviour that existed in 0.0.39 and preventing `CrashLoopBackOff` for such sandboxes.