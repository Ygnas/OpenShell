# Code Review: Ygnas/OpenShell PR #1

**Title:** Fix recursive chown to skip read-only sub-mounts  
**URL:** https://github.com/Ygnas/OpenShell/pull/1  
**Review posted:** https://github.com/Ygnas/OpenShell/pull/1#pullrequestreview-4707758593

---

## What Was Checked

1. **Core logic change** (`crates/openshell-supervisor-process/src/process.rs`): The hand-rolled recursive `chown_sandbox_home` was replaced with a `walkdir::WalkDir` traversal. Reviewed error handling, symlink treatment, and whether the EROFS-skip logic is correct and complete.
2. **Dependency additions** (`Cargo.toml`, `crates/openshell-supervisor-process/Cargo.toml`): `walkdir = "2.3"` added to workspace and crate. `libc`, `nix`, `walkdir` added to `[dev-dependencies]`. All look appropriate.
3. **Inline unit test** (`process.rs` `mod tests`): The new test `chown_sandbox_home_skips_readonly_submount` that mounts a read-only tmpfs and calls the production function.
4. **External integration test** (`tests/sandbox_chown.rs`): Three tests — one happy-path walk, one error-propagation check, one ownership-verification check.
5. **Docker integration test** (`tests/integration/sandbox_readonly_mount.rs`): Gated behind `CI_PRIVILEGED`; launches a container and checks the supervisor exits cleanly.
6. **CI workflow** (`.github/workflows/branch-checks.yml` referenced in PR description but not in the diff): Not directly reviewable from the diff; noted in issues below.

---

## Issues Found

### Issue 1 — EROFS-only filter is too narrow

**File:** `crates/openshell-supervisor-process/src/process.rs`, the `Err(Errno::EROFS)` match arm in `chown_sandbox_home`

**What is wrong:** Because `follow_links(false)` is set, `chown` operates on symlink inodes via `lchown`; on Linux, `lchown` and `chown` on entries under a read-only bind-mount or overlayfs can return `EPERM` instead of `EROFS`, so those paths will not be skipped and will instead cause the walk to abort with an error.

**Fix:** Also match `Errno::EPERM` in the skip arm (or, for tighter safety, check `entry.metadata().permissions().readonly()` before calling chown and skip accordingly).

---

### Issue 2 — `chown_walk_propagates_non_erofs_errors` test is a no-op

**File:** `crates/openshell-supervisor-process/tests/sandbox_chown.rs`, lines 388–394

**What is wrong:** The test only asserts that `Errno::EROFS != Errno::EACCES` and `Errno::EROFS != Errno::EPERM` — it never calls the walk logic — so it gives zero coverage of the error-propagation path it claims to verify.

**Fix:** Replace it with a test that invokes the walk against a directory where `chown` will return a non-EROFS error (e.g. via `chmod 000` on a directory to force `EPERM`) and asserts the function returns `Err`.

---

### Issue 3 — Doc-comment incorrectly claims EROFS on root is propagated

**File:** `crates/openshell-supervisor-process/src/process.rs`, the doc-comment above `chown_sandbox_home`

**What is wrong:** The comment states "If `root` itself is on a read-only filesystem the error is propagated," but `root` is the first entry emitted by `WalkDir::new(root)` and falls into the same `Errno::EROFS => warn + continue` branch, so it is silently skipped rather than propagated — the comment is incorrect.

**Fix:** Either add an explicit `chown(root, uid, gid)` call before the `WalkDir` loop that returns its error without swallowing it, or update the comment to accurately say that EROFS on the root is also skipped with a warning.

---

## Overall Assessment

The approach is correct and addresses the real crash scenario (EROFS from a read-only sub-mount during startup). The use of `walkdir` simplifies the code and the RAII unmount guard in the test is a good practice. However, the EROFS-only error filter is likely incomplete in production (Issue 1), one of the three new tests is effectively dead code (Issue 2), and a doc-comment makes a false claim about the safety guarantee for the root path (Issue 3). These should be addressed before merging.
