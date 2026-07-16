# Changes to PR #7 — Fix recursive chown to skip read-only submounts

## File modified

`crates/openshell-supervisor-process/src/process.rs`

Commit: `fb0a2e402c47ec3e975be80b6ebe4d295751420d` on branch `fix/erofs-readonly-submount-chown`.

---

## Issue 1: Eliminate O(D×M) repeated `/proc/self/mountinfo` reads

**Problem:** The original `is_readonly_mount(path)` opened and fully parsed
`/proc/self/mountinfo` on every call. It was called inside the `for entry in
entries` loop inside the recursive `chown_sandbox_home`, so for a sandbox tree
with *D* directories and *M* mount entries this performed *O(D × M)* file
reads.

**Fix:** Split the function into two:

- `parse_readonly_mounts() -> io::Result<HashSet<PathBuf>>` — opens
  `/proc/self/mountinfo` once and returns a set of all read-only mount point
  paths.
- `is_readonly_mount(canonical: &Path, readonly_mounts: &HashSet<PathBuf>) -> bool`
  — performs a pure in-memory longest-prefix match against the pre-parsed set.

`chown_sandbox_home` now accepts `readonly_mounts: &HashSet<PathBuf>` as an
additional parameter and passes it through the recursion unchanged. The caller,
`prepare_filesystem`, calls `parse_readonly_mounts()` exactly once before the
walk begins.

---

## Issue 2: Log I/O errors instead of silently discarding them

**Problem:** The original code used `.unwrap_or(false)` on the
`is_readonly_mount` result, silently swallowing any I/O error (e.g. `/proc`
not mounted, permission denied). This made failures invisible and could cause
the code to proceed as if a path were writable when it is not.

**Fix:** In `prepare_filesystem`, `parse_readonly_mounts()` is now wrapped with
`.unwrap_or_else(|e| { warn!(..., error = %e, ...); HashSet::new() })`. If
`/proc/self/mountinfo` is inaccessible, a structured `warn!` message is emitted
including the underlying error before falling back to an empty set. Added
`warn` to the `tracing` import.

The fallback to an empty set is safe: EROFS errors on individual files are
still caught and tolerated in the `match chown(...)` block, so supervisor
startup is not interrupted even without mount-point detection.

---

## Issue 3: Cache `path.is_dir()` to avoid double `stat` syscall

**Problem:** After the symlink guard, `path.is_dir()` was called twice per
non-symlink entry: once in the `is_readonly_mount` guard condition, and again
in the `if path.is_dir()` recursion branch. Each call issues a `stat` syscall.

**Fix:** Introduced `let is_dir = path.is_dir();` immediately after the symlink
guard. Both the read-only-mount check and the recursion branch now use the
cached `is_dir` value, halving the number of `stat` calls per entry.

---

## Test updates

All three existing `chown_sandbox_home` test call sites were updated to pass an
empty `HashSet::new()` for the new `readonly_mounts` parameter. Test behaviour
is unchanged.
