**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On Kubernetes driver sandboxes the supervisor performs a *recursive* `chown /sandbox` during startup.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` `emptyDir` mounted at `/sandbox/.openclaw/skills`), the recursive chown hits that mount and fails with `EROFS`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
The problem surfaced after upgrading to OpenShell 0.0.82; it worked in 0.0.39.

## Approach
1. **Detect read‑only mounts**  
   * Use `nix::sys::statfs::statfs` to read the mount flags for a given path.  
   * If `MS_RDONLY` is set, the path is on a read‑only mount.

2. **Skip chown on read‑only mounts**  
   * In the recursive chown routine, before calling `chown` on a file/directory, check if the path is on a read‑only mount.  
   * If it is, log a warning and continue without attempting to change ownership.

3. **Keep behaviour for writable mounts**  
   * For all other paths, keep the existing recursive chown logic unchanged.

4. **Add tests**  
   * Create a temporary sandbox directory.  
   * Bind‑mount a sub‑directory as read‑only and run the recursive chown routine.  
   * Verify that:  
     * All writable files are owned by the sandbox UID/GID.  
     * The read‑only sub‑mount is left untouched and no error is returned.

5. **Documentation & Logging**  
   * Add a comment explaining why read‑only mounts are skipped.  
   * Emit a `warn!` log when a read‑only mount is skipped so operators can see the behaviour.

## Files to Modify / Create
| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or wherever the recursive chown is implemented) | Add helper `is_read_only_mount(path: &Path) -> bool`.  Update the chown loop to call this helper and skip read‑only mounts. |
| `crates/openshell-supervisor/src/sandbox.rs` | Add `use nix::sys::statfs::statfs;` and `use nix::sys::statfs::MsFlags;` |
| `crates/openshell-supervisor/src/sandbox.rs` | Add `use log::warn;` |
| `tests/sandbox_chown.rs` | New integration test that mounts a read‑only sub‑directory and verifies behaviour. |
| `Cargo.toml` (supervisor crate) | Ensure `nix` is listed as a dependency (already present in most OpenShell crates). |
| `README.md` (optional) | Add a note in the “Sandbox” section that read‑only sub‑mounts are now supported. |

### Helper Function (pseudo‑code)
```rust
fn is_read_only_mount(path: &Path) -> bool {
    match statfs(path) {
        Ok(fs) => fs.flags() & MsFlags::MS_RDONLY != 0,
        Err(_) => false, // conservative: treat unknown as writable
    }
}
```

### Recursive Chown Update (pseudo‑code)
```rust
for entry in WalkDir::new("/sandbox") {
    let path = entry.path();
    if is_read_only_mount(path) {
        warn!("Skipping chown on read‑only mount: {:?}", path);
        continue;
    }
    // existing chown logic
}
```

## Considerations
| Edge Case | Mitigation |
|-----------|------------|
| **Bind mounts** – `statfs` correctly reports `MS_RDONLY` for bind mounts that are read‑only. |
| **Nested read‑only mounts** – The helper is called for every entry; nested read‑only mounts are also skipped. |
| **Permission errors on writable mounts** – Preserve original error handling; only skip when `MS_RDONLY` is set. |
| **Performance** – `statfs` is inexpensive; called once per entry. |
| **Logging noise** – Only log a warning when a read‑only mount is encountered; this is expected in many workflows. |
| **Testing** – Use `tempfile` and `nix::mount::mount` to create a read‑only bind mount in the test. |
| **Compatibility** – No changes to the driver or agent; only the supervisor binary is affected. |

## Summary
Implement a read‑only mount check in the supervisor’s recursive chown routine, skip chowning those mounts, and add tests to verify the behaviour. This will prevent `EROFS` crashes while preserving correct ownership on writable parts of the sandbox.