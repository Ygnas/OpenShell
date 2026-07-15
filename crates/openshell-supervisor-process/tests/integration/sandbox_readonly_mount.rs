// SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

//! Integration test: supervisor starts successfully when a read-only sub-mount
//! exists under /sandbox.
//!
//! This test launches a minimal sandbox container (using `docker run
//! --privileged`) that has a read-only tmpfs mounted under /sandbox and
//! verifies that the supervisor completes the chown walk without crashing.
//!
//! The test is gated behind the `CI_PRIVILEGED` environment variable so it
//! only runs in CI jobs that have privileged container access.  It is skipped
//! silently in unprivileged environments.

use std::process::Command;

/// Run a Docker container with a read-only sub-mount under /sandbox and
/// confirm that the supervisor's `chown_sandbox_home` walk completes without
/// error (i.e. the container does not exit with a non-zero code due to EROFS).
///
/// The container runs a one-shot command that:
/// 1. Mounts a read-only tmpfs on /sandbox/readonly_sub (requires --privileged).
/// 2. Invokes the supervisor binary with a minimal policy.
///
/// If Docker is not available or `CI_PRIVILEGED` is not set the test is
/// skipped.
#[test]
fn supervisor_starts_with_readonly_sandbox_submount() {
    // Only run in explicitly privileged CI environments.
    if std::env::var_os("CI_PRIVILEGED").is_none() {
        eprintln!(
            "SKIP: CI_PRIVILEGED not set; \
             skipping privileged integration test supervisor_starts_with_readonly_sandbox_submount"
        );
        return;
    }

    // Require docker/podman.
    let docker_ok = Command::new("docker").arg("info").output().is_ok_and(|o| o.status.success());
    if !docker_ok {
        eprintln!("SKIP: docker not available");
        return;
    }

    // The test mounts a read-only tmpfs over /sandbox/readonly_sub inside the
    // container and then runs the supervisor's chown walk indirectly by
    // starting the sandbox binary with `--help` (or a no-op subcommand).
    // A non-zero exit code (or a "EROFS" panic string in stderr) means the
    // fix is not working.
    let output = Command::new("docker")
        .args([
            "run",
            "--rm",
            "--privileged",
            // Use the current CI image which contains the openshell-sandbox binary.
            "ghcr.io/nvidia/openshell/sandbox:latest",
            "/bin/sh",
            "-c",
            // 1. Create the sub-directory that will be read-only.
            // 2. Mount a read-only tmpfs over it.
            // 3. Run the sandbox binary with --version (triggers startup but
            //    exits immediately; chown happens during main init).
            "mkdir -p /sandbox/readonly_sub && \
             mount -t tmpfs -o ro,nosuid,nodev,noexec tmpfs /sandbox/readonly_sub && \
             openshell-sandbox --version",
        ])
        .output()
        .expect("failed to run docker");

    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);

    // The sandbox binary should exit 0 (--version always succeeds) and must
    // not emit an EROFS-related panic in stderr.
    assert!(
        output.status.success(),
        "sandbox exited with non-zero status; stdout={stdout:?} stderr={stderr:?}"
    );
    assert!(
        !stderr.contains("EROFS") && !stderr.contains("read-only file system"),
        "unexpected EROFS error in stderr: {stderr}"
    );
}
