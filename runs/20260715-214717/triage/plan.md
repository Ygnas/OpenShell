**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On Kubernetes compute driver (0.0.82) the sandbox supervisor performs a
recursive `chown /sandbox` during startup.  
If a read‑only volume is mounted under `/sandbox` (e.g. `/sandbox/.openclaw/skills`),
the recursive chown hits the read‑only mount and aborts with `EROFS`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
The same pod spec worked on 0.0.39, so the regression is tied to the
current supervisor implementation.

## Approach
1. **Detect read‑only mount points**  
   * Parse `/proc/self/mountinfo` once at startup.  
   * Build a `HashSet<PathBuf>` of mount points that have the `ro` option.  
   * Store this set in a small helper struct (`ReadonlyMounts`) that can be
     queried during the chown walk.

2. **Recursive chown with error handling**  
   * Replace the current single `chown -R /sandbox` call with a Rust walk
     that iterates over every entry under `/sandbox`.  
   * For each entry:
     * Skip symlinks (they are not owned by the sandbox UID/GID).  
     * If the entry’s path is inside a read‑only mount point, skip the
       entire subtree (`WalkDir::skip_current_dir`).  
     * Attempt `nix::unistd::chown`.  
     * If the error is `EROFS`, silently skip the entry (the mount is
       read‑only).  
     * For any other error, propagate it – we still want to fail on
       permission problems that are not due to a read‑only mount.

3. **Integration**  
   * Add the helper struct and the new recursive chown function to the
     supervisor crate (`crates/openshell-supervisor/src/sandbox.rs` or the
     module that currently performs the chown).  
   * Replace the old call with the new function.  
   * Keep the public API unchanged – the supervisor still performs a
     recursive chown on `/sandbox` but now ignores read‑only submounts.

4. **Testing**  
   * Add a new integration test (`tests/readonly_mount.rs`) that:
     * Creates a temporary directory as the sandbox root.  
     * Mounts a read‑only `tmpfs` (or `bind`‑mount with `ro`) under a
       subdirectory.  
     * Calls the new recursive chown helper and asserts that it returns
       `Ok(())` and that the writable parts are owned correctly.  
   * Skip the test when not running as root or when `mount` is not
     available (CI may run as non‑root).

5. **Dependencies**  
   * The repository already uses `walkdir` and `nix`; no new dependencies
     are required.  
   * Add a small helper function to parse mountinfo – no external crate
     needed.

6. **Documentation & Logging**  
   * Add a comment explaining why read‑only mounts are skipped.  
   * Log a warning when a read‑only mount is detected and skipped
     (optional, can be gated behind a debug flag).

## Files to Modify / Add

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or the module that does the chown) | • Add `ReadonlyMounts` struct with `new() -> Self` that parses `/proc/self/mountinfo`. <br>• Add `is_readonly_mount(&self, path: &Path) -> bool`. <br>• Add `recursive_chown_skip_ro(root: &Path, uid: Uid, gid: Gid, readonly_mounts: &ReadonlyMounts) -> Result<()>`. <br>• Replace existing recursive chown call with the new function. |
| `crates/openshell-supervisor/src/sandbox.rs` | • Update imports: `use std::collections::HashSet; use std::path::Path; use nix::unistd::{Uid, Gid, chown}; use walkdir::WalkDir;` |
| `crates/openshell-supervisor/src/sandbox.rs` | • Add unit tests for `ReadonlyMounts::new` (optional). |
| `tests/readonly_mount.rs` | • New integration test that mounts a read‑only subdirectory and verifies chown. |
| `Cargo.toml` (supervisor crate) | • No changes needed (dependencies already present). |

## Considerations

| Edge Case | Handling |
|-----------|----------|
| **Nested read‑only mounts** | `ReadonlyMounts` stores all read‑only mount points; `is_readonly_mount` checks if the path starts with any of them, so nested mounts are correctly skipped. |
| **Symlinks** | Symlinks are skipped to avoid changing the target’s ownership. |
| **Non‑root execution** | The supervisor runs as root inside the sandbox; the test will skip if not root. |
| **Performance** | The walk is performed once at startup; the overhead is negligible compared to the previous single `chown -R`. |
| **Other errors** | Only `EROFS` is ignored; all other errors propagate to keep the supervisor safe. |
| **Mountinfo format changes** | The parser is tolerant: it splits on spaces and looks for the `ro` option in the mount‑options field. |
| **CI environment** | The integration test is gated behind `#[cfg(target_os = "linux")]` and `#[cfg(unix)]` and will skip if `mount` is not available. |

## Summary of Steps

1. Implement `ReadonlyMounts` and the recursive chown helper in the supervisor crate.  
2. Replace the old chown logic with the new helper.  
3. Add the integration test for read‑only submounts.  
4. Run `cargo test` locally and in CI.  
5. Verify that a sandbox with a read‑only submount starts successfully on 0.0.82.  
6. Commit, push, and close the issue.

--- 

**End of plan** 
```