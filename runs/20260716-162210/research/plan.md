**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
When the Kubernetes driver starts a sandbox, the supervisor performs a **recursive `chown /sandbox`** to set the sandbox UID/GID.  
If any sub‑path under `/sandbox` is a **read‑only mount** (e.g. a `readOnly: true` volume mounted into the workspace), the recursive chown hits that mount and fails with `EROFS: Read‑only file system`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
This behaviour was introduced in 0.0.82; it did not exist in 0.0.39.

## Approach
1. **Detect read‑only mounts** – use `statfs` to read the mount flags (`MS_RDONLY`).  
2. **Skip chown on read‑only mounts** –  
   * If the current path is a read‑only mount, return `Ok(())` and do not recurse into it.  
   * If a `chown` call returns `EROFS`, treat it as a no‑op and continue.  
3. **Keep existing behaviour for all other errors** – propagate any other error from `chown` or filesystem traversal.  
4. **Add a small helper** `is_readonly_mount(path: &Path) -> bool`.  
5. **Update imports** – bring in `nix::sys::statfs` and `nix::sys::statfs::MsFlags`.  
6. **Add unit tests** (optional) to verify that `is_readonly_mount` works on a temporary mount and that `chown_recursive` ignores `EROFS`.  
7. **Update Cargo.toml** – ensure the `nix` crate is present (it already is in the repo, but double‑check the version).  

### Why this works
* `statfs` is the canonical way to query mount flags on Linux.  
* Skipping the subtree that is read‑only guarantees that the supervisor never attempts to modify a read‑only filesystem.  
* Ignoring `EROFS` errors keeps the behaviour identical to the previous version for all other paths.  

## Files to modify / create

| File | Change |
|------|--------|
| `src/sandbox.rs` (or wherever `chown_recursive` lives) | <ul><li>Import `nix::sys::statfs::{statfs, MsFlags}`.</li><li>Add helper `fn is_readonly_mount(path: &Path) -> bool` that returns `true` if `statfs(path).ok().map(|s| s.f_flags & MsFlags::MS_RDONLY != 0).unwrap_or(false)`.</li><li>Modify the recursive chown routine to: <ul><li>Skip the current path if `is_readonly_mount(path)`.</li><li>After calling `chown`, if the error is `nix::errno::Errno::EROFS`, treat it as success and continue.</li></ul></li></ul> |
| `src/sandbox.rs` | Add unit tests under `#[cfg(test)]` to verify: <ul><li>`is_readonly_mount` returns `true` for a temporary read‑only bind mount.</li><li>`chown_recursive` returns `Ok(())` when encountering a read‑only mount (mocked or real).</li></ul> |
| `Cargo.toml` | Ensure `nix = { version = "0.26", features = ["fs"] }` (or the current repo version). |

> **Note**: If the recursive chown logic lives in a different module (e.g. `src/supervisor.rs`), apply the same changes there.

## Considerations

| Edge case | Handling |
|-----------|----------|
| **Symlinks** | Use `symlink_metadata` to avoid following symlinks; skip them as the supervisor already does. |
| **Non‑existent paths** | `statfs` will fail; treat as *not* read‑only and let the normal chown error propagate. |
| **Mounts that become read‑only after chown** | The check is performed before chown; if the mount becomes read‑only later, the chown will fail with `EROFS` and we ignore it. |
| **Performance** | `statfs` is inexpensive; the extra call per directory is negligible compared to the overall startup time. |
| **Testing** | Creating a real read‑only bind mount in CI may require `sudo`. If that is not possible, the unit test can be skipped or use a mock. |
| **Other drivers** | The change is safe for all drivers; it simply makes the chown more tolerant of read‑only mounts. |
| **Security** | Skipping a read‑only mount does not expose any new attack surface; it merely avoids an error. |

## Summary of changes

1. Add `is_readonly_mount` helper.  
2. Update recursive chown to skip read‑only mounts and ignore `EROFS`.  
3. Add necessary imports.  
4. Add optional unit tests.  
5. Verify `Cargo.toml` has the `nix` dependency.

Once these changes are merged, the supervisor will no longer crash when a sandbox contains read‑only sub‑mounts, restoring the behaviour that existed in 0.0.39 and earlier.