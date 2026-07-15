# Implementation Summary

## Pull Request

**URL:** https://github.com/Ygnas/OpenShell/pull/1  
**Branch:** `fix/sandbox-chown-readonly-mounts`  
**Base:** `main`

---

## Problem

On the Kubernetes driver, the sandbox supervisor performs a recursive `chown /sandbox` during startup to set the sandbox UID/GID. If any sub-mount under `/sandbox` is read-only (e.g. a `readOnly: true` volume), the recursive chown hits that mount and aborts with `EROFS`. The agent never starts and the pod ends up in `CrashLoopBackOff`.

---

## Approach

The root cause is in `chown_sandbox_home` in `crates/openshell-supervisor-process/src/process.rs`. The old implementation used a manual recursive descent (`read_dir` + recursion) and propagated all errors unconditionally — including `EROFS`.

The fix replaces the implementation with:

1. **`walkdir::WalkDir`** for the directory traversal (eliminates recursion, more robust).
2. **Per-entry `EROFS` handling**: if `nix::unistd::chown` returns `EROFS`, log a `warn!` and continue the walk. All other errors are still propagated immediately.
3. The **symlink-at-root guard** is preserved: if the root path itself is a symlink, the function returns an error (privilege escalation prevention).

---

## Files Modified

| File | Change |
|------|--------|
| `crates/openshell-supervisor-process/src/process.rs` | Replaced `chown_sandbox_home` with `walkdir`-based implementation; added `chown_sandbox_home_skips_readonly_submount` unit test. |
| `crates/openshell-supervisor-process/Cargo.toml` | Added `walkdir = { workspace = true }` to `[dependencies]`; added `libc`, `nix`, `walkdir` to `[dev-dependencies]` for external test crates. |
| `Cargo.toml` (workspace) | Added `walkdir = "2.3"` to `[workspace.dependencies]`. |

## Files Created

| File | Change |
|------|--------|
| `crates/openshell-supervisor-process/tests/sandbox_chown.rs` | External integration tests using `libc::mount` to create a real read-only tmpfs sub-mount and verifying the chown walk succeeds. Tests self-skip if `CAP_SYS_ADMIN` is absent. |
| `crates/openshell-supervisor-process/tests/integration/sandbox_readonly_mount.rs` | Docker-based integration test that launches a minimal sandbox container with a read-only sub-mount and verifies the sandbox binary starts without error. Gated behind `CI_PRIVILEGED` env var. |
| `.github/workflows/branch-checks.yml` | Added a new `rust-privileged` job that runs the external integration tests in `--privileged` mode with `CI_PRIVILEGED=1`. (Note: write access to `.github/workflows/` was blocked by the API policy; this change was prepared locally but requires a CI admin to apply or the branch permissions to be relaxed.) |

---

## Key Implementation Detail

```rust
// New chown_sandbox_home (simplified)
for entry in WalkDir::new(root).follow_links(false) {
    let entry = entry?;
    let path = entry.path();

    match chown(path, uid, gid) {
        Ok(()) => { /* success */ }
        Err(Errno::EROFS) => {
            warn!(path = %path.display(), "Skipping read-only path (EROFS)");
            // continue walking — writable siblings are still chowned
        }
        Err(err) => return Err(miette::miette!("Failed to chown '{}': {err}", path.display())),
    }
}
```

- `WalkDir` by default does **not** follow symlinks (`follow_links(false)`), so symlink inodes are chowned directly (harmless) rather than followed.
- The symlink-at-root check is retained before the walk begins.
- Writable paths continue to be chowned correctly.
- The `EROFS` skip is surgical — only that specific errno is tolerated.

---

## Test Coverage Added

1. **`chown_sandbox_home_skips_readonly_submount`** (in-process unit test in `process.rs`): Mounts a read-only tmpfs on a sub-directory, runs the production function, asserts it returns `Ok(())`. Skips if `CAP_SYS_ADMIN` is unavailable.

2. **`chown_walk_succeeds_with_readonly_submount`** (external test in `tests/sandbox_chown.rs`): Same scenario, exercised via the walkdir + nix::chown primitives directly.

3. **`chown_walk_sets_ownership_on_writable_paths`** (external test in `tests/sandbox_chown.rs`): Verifies that writable files still get the expected UID/GID when a read-only sub-mount is present.

4. **`supervisor_starts_with_readonly_sandbox_submount`** (Docker integration test in `tests/integration/sandbox_readonly_mount.rs`): Runs a full privileged container with a read-only tmpfs mounted under `/sandbox`, asserts the sandbox binary exits 0 and emits no EROFS-related output.
