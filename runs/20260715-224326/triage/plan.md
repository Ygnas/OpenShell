**/tmp/plan.md**

```markdown
# Implementation Plan – Issue #2294
**Bug**: Kubernetes sandbox crashes with `EROFS` when a read‑only sub‑mount exists under `/sandbox`.  
**Affected version**: 0.0.82 (supervisor binary in the gateway image).  
**Goal**: Make the supervisor ignore read‑only mounts during its recursive `chown /sandbox` step so that the sandbox can start normally.

---

## 1. Issue Summary
During sandbox startup the supervisor performs a recursive `chown /sandbox` to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. an `emptyDir` mounted with `readOnly: true`), the recursive chown hits that mount point and fails with `EROFS`.  
The supervisor aborts, the agent never starts, and the pod ends up in `CrashLoopBackOff`.  
This behaviour was introduced in 0.0.82; earlier releases silently ignored the error.

---

## 2. Approach

1. **Locate the recursive chown logic**  
   The supervisor binary is built from `crates/openshell-supervisor`.  
   The recursive chown is implemented in `src/sandbox.rs` (or a similarly named file).  
   It currently walks the `/sandbox` tree and calls `nix::unistd::chown` on every file/directory.

2. **Detect read‑only mounts**  
   *Implement a helper `is_read_only_mount(path: &Path) -> Result<bool, std::io::Error>`* that:
   - Calls `nix::sys::statfs::statfs` on the path.
   - Checks the returned `flags` for `MsFlags::MS_RDONLY`.
   - Returns `true` if the mount is read‑only, otherwise `false`.

   This is lightweight (one system call per directory) and works for all mount types.

3. **Modify the recursive chown**  
   - Before attempting to `chown` a directory, call `is_read_only_mount`.  
   - If the directory is a read‑only mount, skip the `chown` for that directory **and** skip recursing into its subtree.  
   - If `chown` returns `Err(nix::Error::Sys(Errno::EROFS))`, log a warning and continue; propagate all other errors.

4. **Logging**  
   - Use `log::warn!` to emit a message when a read‑only mount is skipped.  
   - Keep the existing success/failure logs for other directories.

5. **Testing**  
   - Add an integration test (`tests/sandbox_chown.rs`) that:
     - Creates a temporary sandbox directory.
     - Mounts a read‑only sub‑directory under it (using `mount` or a loopback device).
     - Runs the chown routine and asserts that it completes without error.
   - Verify that the supervisor still chowns writable directories.

6. **Dependencies**  
   - The supervisor already depends on `nix`; no new crates are required.  
   - Ensure `nix` is at least `0.26` (the current repository version).

---

## 3. Files to Modify / Add

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` | • Add `is_read_only_mount` helper.<br>• Update recursive chown to skip read‑only mounts.<br>• Add error handling for `EROFS`.<br>• Add `log::warn!` statements. |
| `crates/openshell-supervisor/Cargo.toml` | • Verify `nix` dependency is present (>=0.26). |
| `tests/sandbox_chown.rs` *(optional)* | • Integration test for read‑only mount handling. |

> **Note**: If the recursive chown is implemented using the `walkdir` crate, modify the walker to skip entries that are read‑only mounts by checking `is_read_only_mount` on each entry’s path.

---

## 4. Considerations & Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Symlinks** | The current logic skips symlinks; keep this behaviour. |
| **Nested read‑only mounts** | Skipping the top‑level read‑only mount automatically skips all nested entries. |
| **Performance** | `statfs` is inexpensive; calling it once per directory is acceptable. |
| **Mounts with `ro` flag but writable files** | The mount is truly read‑only; skipping is correct. |
| **Other error codes** | Propagate any error other than `EROFS`. |
| **Multiple read‑only mounts** | Each is skipped independently; the supervisor continues. |
| **Testing environment** | The integration test must run with sufficient privileges to perform mounts; use a loopback device or `tmpfs` with `ro` option. |

---

## 5. Acceptance Criteria

1. **No Crash** – A sandbox pod that mounts a read‑only sub‑directory under `/sandbox` starts successfully on 0.0.82.  
2. **Correct Ownership** – All writable files/directories under `/sandbox` are owned by the sandbox UID/GID.  
3. **Graceful Skipping** – The supervisor logs a warning for each skipped read‑only mount but continues processing.  
4. **No Regression** – Existing functionality (e.g., chown on writable mounts, other drivers) remains unchanged.  
5. **Tests Pass** – All unit/integration tests, including the new read‑only mount test, pass.

---

## 6. Timeline

| Task | Owner | ETA |
|------|-------|-----|
| Locate chown logic | Senior Engineer | 1 day |
| Implement `is_read_only_mount` | Senior Engineer | 1 day |
| Update recursive chown | Senior Engineer | 1 day |
| Add logging | Senior Engineer | 0.5 day |
| Write integration test | QA / Engineer | 1 day |
| Review & merge | Maintainer | 0.5 day |

---

**End of Plan**  
```
```