**/tmp/plan.md**

```markdown
# Issue #2294 – Recursive `chown /sandbox` crashes on read‑only submounts

## Issue
On the Kubernetes driver, the sandbox supervisor performs a recursive `chown /sandbox` during startup to set the sandbox UID/GID.  
If any sub‑mount under `/sandbox` is read‑only (e.g. a `readOnly: true` volume), the recursive chown hits that mount and aborts with `EROFS`.  
The agent never starts and the pod ends up in `CrashLoopBackOff`.  
This started happening after the upgrade to **0.0.82**.

## Approach
1. **Locate the recursive chown implementation** – it lives in the supervisor crate (`crates/openshell-supervisor/src/...`).  
2. **Replace the current implementation** with a robust walk that:
   * Iterates over every entry under `/sandbox` using `walkdir::WalkDir`.
   * Calls `nix::unistd::chown` on each entry.
   * Ignores `EROFS` errors (log a warning) and continues walking.
   * Propagates any other error.
3. **Keep the existing behaviour** for writable paths – the function still sets the correct UID/GID on all files that can be modified.
4. **Add unit tests** that:
   * Create a temporary sandbox directory.
   * Mount a read‑only `tmpfs` on a sub‑path.
   * Run the new chown routine and assert that it completes without error.
5. **Add integration test** that runs the supervisor in a minimal sandbox container (using `docker run --privileged` or `podman`) to confirm that the agent starts successfully when a read‑only sub‑mount is present.
6. **Update Cargo.toml** to add `walkdir` (if not already present) and ensure `nix` is available.
7. **Update CI** to run the new tests on all supported platforms.

## Files to modify / create

| File | Change |
|------|--------|
| `crates/openshell-supervisor/src/sandbox.rs` (or the file that contains `chown_sandbox_root`) | Replace the existing recursive chown logic with the new walk‑and‑chown implementation. Add `use walkdir::WalkDir;`, `use nix::unistd::chown;`, `use nix::errno::Errno;`, and `use log::{warn, info};`. |
| `crates/openshell-supervisor/src/sandbox.rs` | Add a helper function `fn chown_sandbox_root(uid: Uid, gid: Gid) -> Result<()>` that implements the walk logic. |
| `crates/openshell-supervisor/src/sandbox.rs` | Update any callers to use the new function (if the function name changed). |
| `crates/openshell-supervisor/Cargo.toml` | Add `walkdir = "2.3"` under `[dependencies]` (if not already present). |
| `tests/sandbox_chown.rs` | New unit test that creates a temp dir, mounts a read‑only tmpfs, runs `chown_sandbox_root`, and asserts success. |
| `tests/integration/sandbox_readonly_mount.rs` | New integration test that launches a minimal sandbox container with a read‑only sub‑mount and verifies that the agent starts. |
| `.github/workflows/ci.yml` | Add the new tests to the test matrix. |

## Considerations

| Edge case | Handling |
|-----------|----------|
| **Root `/sandbox` is read‑only** | The walk will attempt to chown the root directory. If that fails with `EROFS`, we propagate the error because the sandbox cannot be used. |
| **Mount points that are writable** | The walk will chown them normally. No special handling needed. |
| **Symlinks** | `WalkDir` by default does not follow symlinks (`follow_links(false)`), so we will chown the symlink itself (which is harmless). |
| **Performance** | Walking the entire sandbox tree is already required for the original implementation. Adding a simple error check does not add measurable overhead. |
| **Logging** | Use `warn!` to log skipped paths. This keeps the supervisor log readable while still informing operators of the skip. |
| **Test isolation** | The unit test mounts a `tmpfs` read‑only on a sub‑path; this requires `CAP_SYS_ADMIN`. The test will skip if it cannot mount. |
| **CI environment** | The integration test requires privileged mode. It will be gated behind a `privileged` job in the CI matrix. |

## Summary of changes

1. **Recursive chown** – now robust to `EROFS` by walking the tree and ignoring read‑only mounts.
2. **Logging** – warns on skipped paths.
3. **Tests** – unit and integration tests ensure the new behaviour works and regressions are caught.
4. **Dependencies** – added `walkdir` if missing.

Once these changes are merged, the Kubernetes sandbox should start successfully even when read‑only sub‑mounts exist under `/sandbox`.