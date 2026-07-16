# Implementation Summary

## What Was Changed

### Root Cause

The OpenShell supervisor performs a recursive `chown /sandbox` at startup via
`chown_sandbox_home` in
`crates/openshell-supervisor-process/src/process.rs`. When a Kubernetes
sandbox has a read-only volume (e.g. a `ConfigMap` or `Secret`) mounted
under `/sandbox`, the `nix::unistd::chown` syscall returns `EROFS` (read-only
filesystem). The previous code propagated every `chown` error unconditionally,
so `EROFS` caused the entire sandbox startup to abort, placing the pod in
`CrashLoopBackOff`.

---

## Files Modified

| File | Lines changed | Purpose |
|------|--------------|---------|
| `crates/openshell-supervisor-process/src/process.rs` | ~65 lines added/modified | Core fix + unit test |

---

## Approach

### 1. Locate the recursive chown logic

The recursive walk lives in `chown_sandbox_home` (line ~1172 of
`process.rs`). It is called from `prepare_filesystem` whenever a sandbox home
directory needs ownership set before the child process is forked.

### 2. Wrap the `chown` call to ignore `EROFS`

The original code was:

```rust
chown(root, uid, gid).into_diagnostic()?;
```

This was replaced with a `match` that catches `Errno::EROFS` specifically:

```rust
match chown(root, uid, gid) {
    Ok(()) => {}
    Err(Errno::EROFS) => {
        tracing::warn!(
            path = %root.display(),
            "Skipping chown on read-only mount (EROFS) — ownership change not required"
        );
    }
    Err(e) => return Err(e).into_diagnostic(),
}
```

All other `chown` errors (`EPERM`, `ENOENT`, etc.) are still propagated and
abort sandbox startup, preserving existing behaviour for genuine failures.

### 3. Logging

A `warn!`-level structured log is emitted for each path skipped due to `EROFS`.
This is low-noise in normal Docker/VM deployments (where no `EROFS` occurs) but
gives operators a clear signal when the code path is exercised in Kubernetes
with read-only sub-mounts.

### 4. Documentation

The doc-comment on `chown_sandbox_home` was extended to explain that `EROFS`
is intentionally ignored, why it is safe (immutable FS needs no ownership
change), and the scope of the fix (Kubernetes `ConfigMap`/`Secret` volumes).

### 5. Unit test

A new test `chown_sandbox_home_ignores_erofs_on_readonly_mount` was added
inside the existing `#[cfg(test)] mod tests` block. Because creating a genuine
read-only mount requires root privileges (not available in standard CI), the
test:

1. Asserts that the `Errno::EROFS` constant resolves correctly (validates the
   `nix` API surface used by the fix).
2. Exercises the full `chown_sandbox_home` walk over a temporary writable
   directory to confirm the happy path is unaffected.

---

## Pull Request

- **Branch**: `Ygnas:fix/chown-erofs-readonly-submounts`
- **PR URL**: https://github.com/Ygnas/OpenShell/pull/6
- **Target**: `Ygnas/OpenShell` `main` (fork of `NVIDIA/OpenShell`)
- **Commit**: `fix: ignore EROFS when recursively chowning /sandbox on read-only sub-mounts`

---

## Safety Considerations

| Concern | Assessment |
|---------|-----------|
| Ignoring `EROFS` | Safe — an immutable FS cannot change ownership anyway; the chown is a no-op from the FS perspective |
| Other errors still propagate | Yes — only `EROFS` is swallowed; all other errors abort startup |
| Cross-driver impact | Negligible — Docker and VM drivers do not produce `EROFS` under `/sandbox`, so this path is never entered for them |
| Log noise | Low — `warn!` only fires when a read-only mount is encountered, which is not the common case |
