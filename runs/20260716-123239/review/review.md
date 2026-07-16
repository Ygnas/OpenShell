# PR #7 Review — Fix recursive chown to skip read-only submounts

**Repo:** Ygnas/OpenShell  
**PR:** https://github.com/Ygnas/OpenShell/pull/7  
**Event:** COMMENT

## Summary

The PR adds `is_readonly_mount` (a `/proc/self/mountinfo` parser) and updates `chown_sandbox_home` to skip read-only subtrees and tolerate `EROFS` on individual files. The motivation is correct and the high-level design is sound. Three concrete issues were found.

---

## Issue 1: `is_readonly_mount` re-parses `/proc/self/mountinfo` for every directory

**What is wrong:** `is_readonly_mount` is called inside the `for entry in entries` loop of `chown_sandbox_home`, which is recursive. For a tree with *D* directories and *M* mount entries this results in *O(D × M)* file reads of `/proc/self/mountinfo`.

**How to fix:** Parse `/proc/self/mountinfo` once before the walk begins and pass the resulting `HashSet<PathBuf>` of read-only mount points through the recursion (or store it in a shared reference).

---

## Issue 2: `unwrap_or(false)` silently discards I/O errors from `is_readonly_mount`

**What is wrong:** `is_readonly_mount(&path).unwrap_or(false)` swallows any I/O error (e.g. `/proc` not mounted, permission denied) with no log message, causing the code to silently treat the path as writable and potentially hit `EROFS` anyway or miss the read-only detection entirely.

**How to fix:** Log a `warn!` or `debug!` message before falling back to `false` so that failures are observable in production logs.

---

## Issue 3: `path.is_dir()` is called twice per loop iteration

**What is wrong:** After the symlink guard, `path.is_dir()` is evaluated once in the `is_readonly_mount` guard (`if path.is_dir() && is_readonly_mount(...)`) and a second time in the recursion branch (`if path.is_dir()`), issuing two `stat` syscalls for every non-symlink directory entry.

**How to fix:** Bind the result to a local (`let is_dir = path.is_dir();`) before the two checks and reuse it.

---

## Verdict

The fix is well-motivated and the documentation is thorough. The three issues above are the main blockers before merging.
