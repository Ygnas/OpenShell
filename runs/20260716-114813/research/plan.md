**/tmp/plan.md**

```markdown
# Implementation Plan – Issue #2294
**Bug**: Kubernetes sandbox crashes with `EROFS` when a read‑only sub‑mount exists under `/sandbox`.  
**Root cause**: The supervisor performs a *recursive* `chown /sandbox` during startup.  
When the recursive walk encounters a read‑only mount, the `chown` syscall fails with `EROFS`, aborting the sandbox.

---

## Issue
- **Title**: `bug: Kubernetes sandbox crashes EROFS — recursive chown /sandbox fails on read-only submounts (0.0.82)`
- **Environment**: OpenShell 0.0.82, Kubernetes driver, gVisor runtime, read‑only volume mounted under `/sandbox`.
- **Observed**: Supervisor logs show `chown /sandbox` as the last operation before the agent crashes with `CrashLoopBackOff`.

---

## Approach
1. **Locate the recursive chown logic**  
   The supervisor binary (Rust) contains a function that walks `/sandbox` and calls `nix::unistd::chown` on every file/directory.  
   *File*: `crates/openshell-supervisor/src/sandbox.rs` (or the equivalent module that implements `chown_sandbox`).

2. **Modify the walk to ignore `EROFS`**  
   - Wrap the `chown` call in a `match` that checks the returned `Err`.  
   - If the error is `Errno::EROFS`, log a *debug* or *warn* message and continue the walk.  
   - For any other error, propagate it (`return Err(e)`).

3. **Add a helper function (optional)**  
   ```rust
   fn ignore_erofs<F, T>(f: F) -> Result<T, nix::Error>
   where
       F: FnOnce() -> Result<T, nix::Error>,
   {
       match f() {
           Ok(v) => Ok(v),
           Err(nix::Error::Sys(nix::errno::Errno::EROFS)) => Ok(unsafe { std::mem::zeroed() }), // or simply Ok(())
           Err(e) => Err(e),
       }
   }
   ```
   Use this helper around the `chown` call for clarity.

4. **Logging**  
   - Use `log::warn!` or `log::debug!` to emit a message like:  
     `Skipping chown on read‑only mount: /sandbox/.openclaw/skills (EROFS)`.  
   - Keep the log level low to avoid noisy logs in normal operation.

5. **Testing**  
   - Existing unit tests for `chown_sandbox` should still pass.  
   - Add a new test that simulates a read‑only mount by mocking the `chown` call to return `Err(Errno::EROFS)` and verifies that the function continues without propagating the error.  
   - If mocking is too involved, at least ensure that the function returns `Ok(())` when encountering `EROFS`.

6. **Documentation**  
   - Add a comment above the modified code explaining why `EROFS` is ignored.  
   - No changes to external docs are required.

7. **CI & Build**  
   - Run `cargo test` and `cargo clippy` to ensure no lint violations.  
   - Verify that the supervisor binary still builds for all target platforms.

---

## Files to Modify

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or the module containing `chown_sandbox`) | Wrap the recursive `chown` call to ignore `EROFS`. Add logging and optional helper. |
| `tests/sandbox_chown.rs` (or create if not present) | Add a unit test that verifies `EROFS` is ignored. |

---

## Considerations

| Topic | Details |
|-------|---------|
| **Safety** | Ignoring `EROFS` is safe because the file system is immutable; ownership changes are irrelevant. |
| **Other Errors** | All other errors (e.g., permission denied, file not found) should still fail the sandbox to surface real issues. |
| **Performance** | The change is negligible; it only adds a small `match` around each `chown`. |
| **Cross‑driver Impact** | The supervisor is shared across drivers; ignoring `EROFS` will not affect other drivers that do not mount read‑only sub‑directories under `/sandbox`. |
| **Logging Noise** | Use a low log level to avoid flooding logs in normal operation. |
| **Testing** | Simulating a real read‑only mount in unit tests is non‑trivial; a mock of the `chown` syscall is sufficient. |
| **Future** | If a future driver requires chown on read‑only mounts (unlikely), this change can be revisited. |

---

## Summary of Steps

1. **Locate** the recursive chown implementation in the supervisor crate.  
2. **Wrap** the `chown` call to ignore `Errno::EROFS`.  
3. **Log** a warning when skipping.  
4. **Add** a unit test to confirm the behavior.  
5. **Run** CI to ensure all tests pass.  
6. **Commit** and push the change.

Once merged, the Kubernetes sandbox should start successfully even when read‑only sub‑mounts exist under `/sandbox`.