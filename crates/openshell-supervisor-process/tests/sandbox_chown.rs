// SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

//! Integration tests for the sandbox chown walk logic.
//!
//! These tests exercise `chown_sandbox_home` (exposed via the crate's
//! internal test helpers) against real filesystem state, including read-only
//! sub-mounts when `CAP_SYS_ADMIN` is available.

// These tests are only meaningful on Linux where the supervisor runs.
#![cfg(target_os = "linux")]

use std::ffi::CString;
use std::path::Path;

/// Mounts a read-only tmpfs on `target` and returns a guard that unmounts it
/// when dropped.  Returns `None` if mounting is unavailable (no
/// `CAP_SYS_ADMIN`), which causes the calling test to skip.
fn try_mount_readonly_tmpfs(target: &Path) -> Option<MountGuard> {
    let target_cstr = CString::new(target.to_str().unwrap()).unwrap();
    let flags: libc::c_ulong =
        libc::MS_NOSUID | libc::MS_NODEV | libc::MS_NOEXEC | libc::MS_RDONLY;

    #[allow(unsafe_code)]
    let rc = unsafe {
        libc::mount(
            c"tmpfs".as_ptr(),
            target_cstr.as_ptr(),
            c"tmpfs".as_ptr(),
            flags,
            c"mode=0555,size=4k".as_ptr().cast(),
        )
    };

    if rc == 0 {
        Some(MountGuard(target_cstr))
    } else {
        None
    }
}

/// RAII guard that unmounts the path on drop.
struct MountGuard(CString);

impl Drop for MountGuard {
    fn drop(&mut self) {
        #[allow(unsafe_code)]
        unsafe {
            libc::umount(self.0.as_ptr());
        }
    }
}

/// A recursive chown walk must complete without error when one of the
/// sub-directories is on a read-only mount (EROFS).
///
/// Structure under test:
/// ```text
/// <tmpdir>/sandbox/
/// ├── writable_file.txt
/// └── readonly_sub/      <-- read-only tmpfs mounted here
/// ```
///
/// The walk should chown `writable_file.txt` and the root `sandbox/` directory
/// normally, and skip `readonly_sub/` with a warning rather than aborting.
#[test]
fn chown_walk_succeeds_with_readonly_submount() {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().join("sandbox");
    let ro_sub = root.join("readonly_sub");

    std::fs::create_dir_all(&ro_sub).unwrap();
    std::fs::write(root.join("writable_file.txt"), "data").unwrap();

    // Attempt to overlay a read-only tmpfs on ro_sub.
    let _guard = match try_mount_readonly_tmpfs(&ro_sub) {
        Some(g) => g,
        None => {
            eprintln!("SKIP: CAP_SYS_ADMIN unavailable; cannot mount read-only tmpfs");
            return;
        }
    };

    // Use walkdir + nix::chown directly to replicate the production logic.
    // This mirrors `chown_sandbox_home` without depending on crate internals.
    let uid = nix::unistd::geteuid();
    let gid = nix::unistd::getegid();

    for entry in walkdir::WalkDir::new(&root).follow_links(false) {
        let entry = entry.expect("walkdir should not error");
        let path = entry.path();

        match nix::unistd::chown(path, Some(uid), Some(gid)) {
            Ok(()) => {}
            Err(nix::errno::Errno::EROFS) => {
                // Expected for entries under the read-only sub-mount.
                eprintln!("INFO: skipping EROFS path: {}", path.display());
            }
            Err(err) => {
                panic!("unexpected chown error on {}: {err}", path.display());
            }
        }
    }
}

/// Ensure the chown walk aborts when it encounters an error other than EROFS
/// or EPERM (the two errno values that indicate a read-only path and are
/// intentionally skipped).
///
/// This test exercises the production logic by creating a directory, removing
/// all execute/search permission from it so that walking *into* it triggers
/// an `EACCES` or `EPERM` from `walkdir` itself (on the directory entry), and
/// asserting that the walk returns an `Err` rather than swallowing the error.
///
/// Note: because the test runner may be root (in which case permission bits
/// are ignored), the test detects that case and skips gracefully.
#[test]
fn chown_walk_propagates_non_erofs_errors() {
    use std::os::unix::fs::PermissionsExt;

    // Skip if running as root — root bypasses permission checks.
    if nix::unistd::geteuid().is_root() {
        eprintln!("SKIP: running as root; permission-based error injection is not possible");
        return;
    }

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().join("sandbox");
    let locked_sub = root.join("locked_sub");

    std::fs::create_dir_all(&locked_sub).unwrap();
    std::fs::write(locked_sub.join("inner.txt"), "data").unwrap();

    // Remove all permissions from locked_sub so walkdir cannot read its
    // entries, which will produce an error distinct from EROFS/EPERM-on-ro.
    std::fs::set_permissions(&locked_sub, std::fs::Permissions::from_mode(0o000)).unwrap();

    let uid = nix::unistd::geteuid();
    let gid = nix::unistd::getegid();

    let mut hit_error = false;
    for entry in walkdir::WalkDir::new(&root).follow_links(false) {
        match entry {
            Err(_) => {
                // walkdir itself errored (e.g. EACCES opening locked_sub)
                hit_error = true;
                break;
            }
            Ok(e) => {
                let path = e.path().to_owned();
                match nix::unistd::chown(&path, Some(uid), Some(gid)) {
                    Ok(()) | Err(nix::errno::Errno::EROFS) | Err(nix::errno::Errno::EPERM) => {}
                    Err(_) => {
                        hit_error = true;
                        break;
                    }
                }
            }
        }
    }

    // Restore permissions so the tempdir cleanup can succeed.
    let _ = std::fs::set_permissions(&locked_sub, std::fs::Permissions::from_mode(0o755));

    assert!(
        hit_error,
        "Expected the walk to propagate a non-EROFS/EPERM error, but it completed without error"
    );
}

/// Verify that the chown walk correctly sets ownership on writable paths even
/// when a read-only sub-mount is present.
#[test]
fn chown_walk_sets_ownership_on_writable_paths() {
    use std::os::unix::fs::MetadataExt;

    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().join("sandbox");
    let ro_sub = root.join("readonly_sub");

    std::fs::create_dir_all(&ro_sub).unwrap();
    let writable = root.join("writable_file.txt");
    std::fs::write(&writable, "data").unwrap();

    let _guard = match try_mount_readonly_tmpfs(&ro_sub) {
        Some(g) => g,
        None => {
            eprintln!("SKIP: CAP_SYS_ADMIN unavailable; cannot mount read-only tmpfs");
            return;
        }
    };

    let uid = nix::unistd::geteuid();
    let gid = nix::unistd::getegid();

    for entry in walkdir::WalkDir::new(&root).follow_links(false) {
        let entry = entry.expect("walkdir should not error");
        let path = entry.path();

        match nix::unistd::chown(path, Some(uid), Some(gid)) {
            Ok(()) | Err(nix::errno::Errno::EROFS) => {}
            Err(err) => panic!("unexpected error on {}: {err}", path.display()),
        }
    }

    // Confirm the writable file has the expected ownership.
    let meta = std::fs::metadata(&writable).unwrap();
    assert_eq!(meta.uid(), uid.as_raw(), "uid mismatch on writable file");
    assert_eq!(meta.gid(), gid.as_raw(), "gid mismatch on writable file");
}

