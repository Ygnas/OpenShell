**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On Kubernetes driver sandboxes the supervisor performs a *recursive* `chown /sandbox` during startup.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` `emptyDir` mounted at
`/sandbox/.openclaw/skills`), the recursive chown hits that mount and returns `EROFS`.  
The supervisor treats any error as fatal, so the sandbox never starts and the pod ends up in
`CrashLoopBackOff`.  
The problem surfaced after upgrading to OpenShell 0.0.82; it worked on 0.0.39.

## Approach
1. **Locate the recursive chown implementation** – it lives in the supervisor crate
   (`crates/openshell-supervisor/src/identity.rs` in the current code base).  
2. **Replace the existing recursive chown with a tolerant version** that:
   * Walks the directory tree with `walkdir::WalkDir`.
   * Calls `nix::unistd::chown` on every entry.
   * Ignores `EROFS` errors (log a warning and continue).
   * Propagates all other errors.
3. **Keep the existing behaviour for the root `/sandbox`** – the initial `chown` on the
   root directory still succeeds.
4. **Add a small helper function** `chown_recursive_ignore_erofs` to encapsulate the logic.
5. **Update the call site** to use the new helper.
6. **Add a unit test** that mounts a temporary read‑only directory under a sandbox root
   and verifies that the recursive chown does not return an error.
7. **Document the change** in the code comments and in the issue description.

### Why this works
* The sandbox UID/GID must own all writable files under `/sandbox`.  
* Read‑only mounts are intentionally immutable; ownership changes are impossible and
  unnecessary.  
* Ignoring `EROFS` keeps the supervisor robust while preserving the intended behaviour
  for writable paths.

## Files to modify / create

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/identity.rs` | <ul><li>Introduce `chown_recursive_ignore_erofs` helper.</li><li>Replace the existing recursive chown logic with the new helper.</li><li>Import `walkdir::WalkDir`, `nix::unistd::{chown, Uid, Gid}`, `nix::errno::Errno`.</li><li>Log a warning when `EROFS` is encountered.</li></ul> |
| `crates/openshell-supervisor/src/identity.rs` (existing call site) | Update the call to use `chown_recursive_ignore_erofs(&sandbox_root, uid, gid)` instead of the old function. |
| `crates/openshell-supervisor/tests/identity_test.rs` (new) | Add a test that: <ul><li>Creates a temporary sandbox root.</li><li>Mounts a `tmpfs` read‑only sub‑directory under it.</li><li>Runs `chown_recursive_ignore_erofs`.</li><li>Asserts that the function returns `Ok(())` and that writable files are owned correctly.</li></ul> |
| `Cargo.toml` (supervisor crate) | Ensure `walkdir` and `nix` are listed as dependencies (they already are in 0.0.82). |

## Considerations & Edge Cases

| Edge Case | Handling |
|-----------|----------|
| **Multiple nested read‑only mounts** | The walk will hit each mount point; each `EROFS` is ignored, so the walk continues. |
| **Root `/sandbox` is read‑only** | The initial `chown` on `/sandbox` will fail with `EROFS`. This is a user error; we do not silently ignore it because the sandbox cannot function without ownership on the root. |
| **Non‑read‑only mount but permission denied** | Any error other than `EROFS` is propagated; the supervisor will still fail, which is correct. |
| **Performance** | The walk is unchanged; only error handling is altered. |
| **Logging verbosity** | A warning is logged for each ignored `EROFS`. In large sandboxes this could be noisy; consider throttling if needed. |
| **Test environment** | The unit test uses `mount` which requires root privileges. It will be skipped on non‑root CI runners. |

## Summary of Steps

1. **Add helper** `chown_recursive_ignore_erofs` in `identity.rs`.
2. **Replace** the old recursive chown call with the new helper.
3. **Add imports** (`walkdir`, `nix::unistd`, `nix::errno`).
4. **Log** warnings for ignored `EROFS`.
5. **Write unit test** `test_chown_recursive_ignore_erofs`.
6. **Run full test suite** and verify that the sandbox starts correctly with read‑only submounts.
7. **Commit** and open a PR against the main branch.

Once merged, the supervisor will no longer crash when encountering read‑only submounts under `/sandbox`, restoring compatibility with the previous OpenShell 0.0.39 behaviour.