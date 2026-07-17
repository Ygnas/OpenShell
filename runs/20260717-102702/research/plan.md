**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On Kubernetes driver sandboxes the supervisor performs a *recursive* `chown /sandbox` during startup.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` `emptyDir` mounted at
`/sandbox/.openclaw/skills`), the recursive chown hits that mount and returns `EROFS`.  
The supervisor aborts, the agent never starts and the pod ends up in `CrashLoopBackOff`.

The behaviour was fine in 0.0.39‑era; it started failing after the 0.0.82 release.

## Approach
1. **Locate the recursive chown implementation** – it lives in the supervisor crate
   (`crates/openshell-supervisor/src/sandbox.rs` or similar).  
2. **Wrap the `chown` call in error handling** that:
   * Ignores `EROFS` errors (log a warning and continue).
   * Propagates all other errors.
3. **Keep the rest of the logic unchanged** – the supervisor still sets ownership on all
   writable paths.
4. **Add a small integration test** that verifies the supervisor does not crash when a
   read‑only submount is present.  (The test uses a temporary directory and a
   `mount --bind --read-only` to create a real read‑only mount; it requires root
   privileges, so it is gated behind a `#[cfg(any(test, feature = "integration-tests"))]`
   flag and is skipped on CI unless the runner has the necessary permissions.)
5. **Document the change** – update the README / docs to note that read‑only submounts
   are now ignored during the recursive chown.

### Why this works
`chown` on a read‑only filesystem is a benign failure – the ownership of the
read‑only mount does not matter for the sandbox runtime.  Ignoring the error
prevents the supervisor from aborting while still preserving the intended
ownership on all writable parts of the sandbox.

## Files to modify

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or the file that contains `chown_recursive`) | Add error handling around the `nix::unistd::chown` call.  Log a warning on `EROFS` and continue. |
| `crates/openshell-supervisor/src/sandbox.rs` | Add a comment explaining the rationale. |
| `tests/integration/sandbox_chown.rs` | Add a gated integration test that mounts a read‑only subdirectory and verifies the supervisor starts. |
| `Cargo.toml` (supervisor crate) | Add a new optional feature `integration-tests` if not already present. |
| `README.md` / docs | Add a note that read‑only submounts are now ignored during recursive chown. |

### Code snippet (simplified)

```rust
use nix::unistd::chown;
use nix::errno::Errno;
use walkdir::WalkDir;
use std::path::Path;

fn chown_recursive(path: &Path, uid: Uid, gid: Gid) -> Result<()> {
    for entry in WalkDir::new(path).follow_links(false) {
        let entry = entry?;
        let p = entry.path();

        // Skip symlinks – they are handled elsewhere
        if entry.file_type().is_symlink() {
            continue;
        }

        match chown(p, Some(uid), Some(gid)) {
            Ok(_) => {}
            Err(nix::Error::Sys(Errno::EROFS)) => {
                log::warn!(
                    "Skipping read‑only path during chown: {}",
                    p.display()
                );
                // Continue walking the rest of the tree
                continue;
            }
            Err(e) => return Err(e.into()),
        }
    }
    Ok(())
}
```

## Considerations

| Edge case | Impact | Mitigation |
|-----------|--------|------------|
| **Read‑only mount at `/sandbox` itself** | Supervisor would skip the entire sandbox – unlikely but possible. | The code currently only skips the offending path; if `/sandbox` is read‑only the chown will fail on the root and the supervisor will abort.  This is a true failure scenario that cannot be ignored. |
| **Non‑EROFS errors** | Must still abort to surface real problems. | Only `Errno::EROFS` is ignored; all other errors propagate. |
| **Performance** | Minor overhead from logging warnings. | Acceptable; the warning is only emitted once per offending path. |
| **Testing** | Real read‑only mounts require root. | Integration test gated behind `feature = "integration-tests"` and skipped on CI unless the runner has root privileges. |
| **Future driver changes** | If the driver changes the way it injects UID/GID, the chown logic may need to be updated. | The change is isolated to the supervisor; no driver code is touched. |

## Implementation Steps

1. **Patch the supervisor**  
   - Add the error handling snippet above.  
   - Add a comment explaining why `EROFS` is ignored.  
   - Update any `use` statements if necessary.

2. **Add integration test**  
   - Create a temporary directory.  
   - Mount a subdirectory as read‑only using `mount --bind --read-only`.  
   - Start the supervisor in a child process (or use the existing test harness).  
   - Assert that the supervisor exits with success and that the warning is logged.

3. **Update Cargo features**  
   - Add `integration-tests` optional feature to `Cargo.toml` if not already present.  
   - Guard the integration test behind `#[cfg(feature = "integration-tests")]`.

4. **Documentation**  
   - Update the README or relevant docs to mention that read‑only submounts are now ignored during recursive chown.

5. **Commit & PR**  
   - Commit the changes with a clear message:  
     ```
     Fix #2294 – ignore EROFS during recursive chown
     ```
   - Add the integration test to the PR and run the full test suite.

6. **CI**  
   - Ensure the integration test is skipped on CI unless the runner has root privileges.  
   - Verify that all existing tests still pass.

## Expected Outcome

- Sandboxes with read‑only submounts under `/sandbox` start successfully.  
- The supervisor logs a warning for each read‑only path it skips.  
- No other behaviour is affected.  
- The change is fully covered by the new integration test and documented.

--- 

**End of plan** 
```