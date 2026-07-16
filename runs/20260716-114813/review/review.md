# PR #6 Review — fix: ignore EROFS during recursive chown of /sandbox

Repository: Ygnas/OpenShell  
PR: https://github.com/Ygnas/OpenShell/pull/6  
Review event: COMMENT

---

## Issue 1 — Test doesn't cover the EROFS branch (logic gap)

**What is wrong:** The test `chown_sandbox_home_ignores_erofs_on_readonly_mount` only asserts a tautology (`Errno::EROFS == nix::Error::from(Errno::EROFS)`) and then runs the happy path on a writable directory; the EROFS-skipping match arm in `chown_sandbox_home` is never actually invoked, so the core fix is untested.

**How to fix:** Mock or intercept the `chown` syscall (e.g. via a read-only bind-mount when running as root, or by refactoring to accept an injectable chown function) so the test actually exercises the `Err(Errno::EROFS)` arm.

---

## Issue 2 — EROFS handling is only applied to the root path, not recursive entries

**What is wrong:** The EROFS-tolerant `match` wraps only `chown(root, uid, gid)`, but the recursive walk over directory entries (the `read_dir` loop below) still calls `chown` without the same guard; if a read-only sub-mount lives *inside* the sandbox directory rather than at its root, the walk will still abort on EROFS.

**How to fix:** Extract the EROFS-tolerant `match` into a small helper (e.g. `chown_tolerant`) and use it for every `chown` call site in the recursive walk, not just the root.

---

## Issue 3 — Recursive walk silently swallows `read_dir` errors

**What is wrong:** The existing code uses `if let Ok(entries) = std::fs::read_dir(root)`, which silently discards any error opening a directory for iteration; combined with the new EROFS-skip logic, failures to enumerate sub-directories are now completely invisible even when they indicate a real problem.

**How to fix:** Propagate `read_dir` errors (or at minimum log them at `warn` level) so that legitimate enumeration failures are not silently swallowed alongside intentional EROFS skips.
