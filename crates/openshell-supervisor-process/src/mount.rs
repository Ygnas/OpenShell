// SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

//! Mount-point utilities for the process supervisor.
//!
//! Parses `/proc/self/mountinfo` to determine which paths are mounted
//! read-only so that the recursive chown can skip them.

use std::collections::HashSet;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;

/// Return a set of mount points that are currently mounted read-only.
///
/// Parses `/proc/self/mountinfo` (Linux kernel format) and collects every
/// mount point whose per-mount options field contains the bare token `"ro"`.
///
/// The mountinfo format (from `proc(5)`) is:
///
/// ```text
/// <mount_id> <parent_id> <major:minor> <root> <mount_point> <mount_options> …
/// ```
///
/// Field indices (0-based):
/// * 4 – mount point
/// * 5 – per-mount options (e.g. `ro,relatime`)
///
/// # Errors
///
/// Returns an `std::io::Error` if the file cannot be opened or read.
pub fn get_readonly_mount_points() -> std::io::Result<HashSet<PathBuf>> {
    get_readonly_mount_points_from("/proc/self/mountinfo")
}

/// Parse read-only mount points from an arbitrary mountinfo-formatted file.
///
/// Separated from [`get_readonly_mount_points`] so that unit tests can supply
/// a synthetic file without touching `/proc`.
pub(crate) fn get_readonly_mount_points_from(path: &str) -> std::io::Result<HashSet<PathBuf>> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    let mut ro_mounts = HashSet::new();

    for line in reader.lines() {
        let line = line?;
        // mountinfo format (see proc(5)).  Fields are whitespace-separated.
        // We only need:
        //   field 4 – mount point (e.g. /sandbox/config)
        //   field 5 – per-mount options (e.g. ro,relatime)
        // Optional tagged fields (master:N, peer:N, …) may follow; we ignore them.
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 6 {
            continue;
        }
        let mount_point = PathBuf::from(parts[4]);
        let options = parts[5];

        // Check for the bare "ro" token by splitting on commas.  A substring
        // match would produce false positives on options like "proto" or "noro".
        if options.split(',').any(|opt| opt == "ro") {
            ro_mounts.insert(mount_point);
        }
    }
    Ok(ro_mounts)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn write_fake_mountinfo(content: &str) -> tempfile::NamedTempFile {
        let mut file = tempfile::NamedTempFile::new().expect("create tempfile");
        file.write_all(content.as_bytes()).expect("write mountinfo");
        file
    }

    #[test]
    fn detects_readonly_mount_point() {
        let file = write_fake_mountinfo(
            "36 1 8:1 / /ro_mount ro,relatime shared:1 - ext4 /dev/sda1 rw\n",
        );
        let path = file.path().to_str().unwrap().to_string();
        let mounts = get_readonly_mount_points_from(&path).unwrap();
        assert!(
            mounts.contains(&PathBuf::from("/ro_mount")),
            "expected /ro_mount to be detected as read-only"
        );
    }

    #[test]
    fn excludes_readwrite_mount_point() {
        let file = write_fake_mountinfo(
            "37 1 8:2 / /rw_mount rw,relatime shared:2 - ext4 /dev/sdb1 rw\n",
        );
        let path = file.path().to_str().unwrap().to_string();
        let mounts = get_readonly_mount_points_from(&path).unwrap();
        assert!(
            !mounts.contains(&PathBuf::from("/rw_mount")),
            "expected /rw_mount NOT to be detected as read-only"
        );
    }

    #[test]
    fn handles_mixed_mount_points() {
        let content = concat!(
            "36 1 8:1 / /ro_mount ro,relatime shared:1 - ext4 /dev/sda1 rw\n",
            "37 1 8:2 / /rw_mount rw,relatime shared:2 - ext4 /dev/sdb1 rw\n",
            "38 36 8:3 / /ro_mount/nested ro,noatime shared:3 - ext4 /dev/sdc1 ro\n",
        );
        let file = write_fake_mountinfo(content);
        let path = file.path().to_str().unwrap().to_string();
        let mounts = get_readonly_mount_points_from(&path).unwrap();

        assert!(mounts.contains(&PathBuf::from("/ro_mount")));
        assert!(mounts.contains(&PathBuf::from("/ro_mount/nested")));
        assert!(!mounts.contains(&PathBuf::from("/rw_mount")));
    }

    #[test]
    fn skips_malformed_lines() {
        // Lines with fewer than 6 fields must be silently skipped.
        let file = write_fake_mountinfo(
            "short line\n36 1 8:1 / /ro_mount ro,relatime shared:1 - ext4 /dev/sda1 rw\n",
        );
        let path = file.path().to_str().unwrap().to_string();
        let mounts = get_readonly_mount_points_from(&path).unwrap();
        assert!(mounts.contains(&PathBuf::from("/ro_mount")));
    }

    #[test]
    fn does_not_false_positive_on_option_containing_ro_substring() {
        // "proto" and "noro" contain "ro" as a substring but must not trigger
        // a false positive.
        let file = write_fake_mountinfo(
            "39 1 8:4 / /rw_complex rw,proto,noro shared:4 - ext4 /dev/sdd1 rw\n",
        );
        let path = file.path().to_str().unwrap().to_string();
        let mounts = get_readonly_mount_points_from(&path).unwrap();
        assert!(!mounts.contains(&PathBuf::from("/rw_complex")));
    }
}
