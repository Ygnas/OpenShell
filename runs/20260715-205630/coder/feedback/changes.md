# PR #1 Review Feedback — Changes Summary

## Context

PR #1 replaces a hand-rolled recursive `chown` in `chown_sandbox_home` with a
`walkdir`-based walk that gracefully skips read-only sub-mounts. A code review
identified three concrete issues. Two commits were pushed to address all three.

---

## Issue 1 — EROFS-only filter too narrow

**File:** `crates/openshell-supervisor-process/src/process.rs`

**Problem:** The original match arm only caught `Errno::EROFS`. However,
`follow_links(false)` causes `walkdir` to call `lchown` (operating on the
symlink inode) rather than `chown`. On Linux, `lchown` on entries inside
read-only bind-mounts or overlayfs layers can return `EPERM` instead of
`EROFS`. The EROFS-only filter would therefore propagate and abort the walk on
those mount types.

**Fix:** Extended the match arm to catch both `Errno::EROFS` and
`Errno::EPERM`. Both now trigger the warn-and-continue path.

```rust
// before
Err(Errno::EROFS) => { warn!(...); }

// after
Err(Errno::EROFS) | Err(Errno::EPERM) => { warn!(...); }
```

**Why:** Ensures the fix works on all Linux mount types that back read-only
sub-directories, not just those that surface as `EROFS`.

---

## Issue 2 — `chown_walk_propagates_non_erofs_errors` provided zero coverage

**File:** `crates/openshell-supervisor-process/tests/sandbox_chown.rs`

**Problem:** The test body was:

```rust
assert_ne!(nix::errno::Errno::EROFS, nix::errno::Errno::EACCES);
assert_ne!(nix::errno::Errno::EROFS, nix::errno::Errno::EPERM);
```

This only compared enum variants. It never invoked the walk loop, so the
error-propagation path had no test coverage.

**Fix:** Replaced the test with one that actually exercises the walk:

1. Creates a directory `sandbox/locked_sub/inner.txt` inside a `tempdir`.
2. `chmod 000`s `locked_sub` so that `walkdir` receives `EACCES` when it
   tries to descend into it — an error that is not in the skip list.
3. Runs the production-mirroring walk loop (same structure as
   `chown_sandbox_home`).
4. Asserts that `hit_error` is `true`, confirming non-EROFS/EPERM errors
   are not swallowed.
5. Restores permissions to `0o755` before the `tempdir` RAII guard drops,
   so cleanup succeeds.
6. Skips gracefully when `geteuid()` is root (root ignores permission bits,
   so the injection technique would not trigger an error).

**Why:** The test now provides actual coverage that the propagation path
works, rather than just comparing constant enum values.

---

## Issue 3 — Doc-comment incorrectly described root EROFS behaviour

**File:** `crates/openshell-supervisor-process/src/process.rs`

**Problem:** The doc-comment on `chown_sandbox_home` stated:

> If `root` itself is on a read-only filesystem the error is propagated
> because the sandbox home directory cannot be used.

This was incorrect. `WalkDir::new(root)` yields `root` as its first entry,
so the root directory hits the exact same `warn + continue` branch as any
other entry. The error is silently skipped, not propagated.

**Fix:** Corrected the doc-comment to accurately reflect the behaviour:

> Note: `root` itself is yielded as the first `WalkDir` entry, so if the
> root directory is on a read-only filesystem it will be silently skipped
> rather than propagated. Callers that require the root to be writable
> should perform an explicit pre-check before calling this function.

**Why:** Accurate documentation prevents future callers from relying on a
guarantee the function does not actually provide.
