# Opt-in OpenSSL Backend and FIPS CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an opt-in system-OpenSSL backend while keeping AWS-LC as the default and add fork-safe CI for the OpenSSL/FIPS build path.

**Architecture:** Move the existing standalone OpenSSL contract implementation into `openshell-crypto` behind an `openssl` feature. Keep the default `aws-lc` feature unchanged and reject simultaneous backend selection at compile time. Retain the standalone validation harness as a focused integration test and run it from a secret-free GitHub Actions workflow. Product-wide gateway/supervisor feature propagation remains a follow-up because it must be threaded through the internal Cargo graph.

**Tech Stack:** Rust Cargo features, OpenSSL 3 via `openssl` 0.10, `rustls-openssl`, `jsonwebtoken-openssl`, GitHub Actions, UBI/Debian build containers.

**Spec:** `docs/superpowers/specs/2026-09-23-openssl-opt-in-backend-design.md`

## Global Constraints

- AWS-LC remains the default upstream backend.
- OpenSSL selection is not a FIPS compliance claim.
- Existing AES-GCM envelope and PKCS#8 compatibility must remain unchanged.
- Pull-request CI must not expose secrets to forked code or publish images.
- Use `apply_patch` for source edits and conventional commits with signoff if committing.

## Review Focus

- Backend feature selection must not silently compile both AWS-LC and OpenSSL.
- OpenSSL key import/signing must preserve the existing `pki::KeyPair` contract.
- The OpenSSL AES-GCM output must preserve nonce/tag layout and error opacity.
- The default workspace build must remain independent of system OpenSSL.
- CI must build and scan locally without requiring registry or signing secrets.

### Task 1: Integrate the OpenSSL backend module

**Files:**
- Create: `crates/openshell-crypto/src/openssl.rs`
- Modify: `crates/openshell-crypto/Cargo.toml`
- Modify: `crates/openshell-crypto/src/lib.rs`
- Modify: `crates/openshell-crypto/README.md`

- [ ] Add mutually exclusive `aws-lc` and `openssl` feature guards.
- [ ] Move the POC primitive, PKI, JWT, and Rustls adapter implementation into `openssl.rs`.
- [ ] Add optional OpenSSL/provider dependencies and feature wiring.
- [ ] Preserve AWS-LC default construction and add OpenSSL construction when selected.
- [ ] Run formatting and focused default-feature tests.

### Task 2: Exercise both backend contracts

**Files:**
- Modify: `examples/openssl-crypto-poc/Cargo.toml`
- Modify: `examples/openssl-crypto-poc/src/lib.rs`
- Modify: `examples/openssl-crypto-poc/tests/contract.rs`
- Modify: `crates/openshell-crypto/tests/` as needed

- [ ] Make the example consume the production OpenSSL backend rather than duplicate it.
- [ ] Keep the independent OpenSSL workspace so normal workspace builds do not require OpenSSL.
- [ ] Run the existing OpenSSL contract suite and default AWS-LC tests.
- [ ] Verify dynamic linkage and absence of AWS-LC/Ring in the OpenSSL example dependency graph.

### Task 3: Add fork-safe FIPS CI

**Files:**
- Create: `.github/workflows/fips-openssl.yml`
- Modify: `examples/openssl-crypto-poc/README.md`

- [ ] Trigger on `pull_request` and `workflow_dispatch`.
- [ ] Build/test the OpenSSL example in a reproducible Linux environment.
- [ ] Run dependency and linkage checks without registry credentials or publishing.
- [ ] Keep any image-push or FIPS-host runtime qualification out of PR jobs.
- [ ] Document fork behavior and the boundary between artifact scanning and runtime FIPS evidence.

### Task 4: Verify and review

- [ ] Run `cargo fmt --check` for the touched Rust workspaces.
- [ ] Run default `cargo test -p openshell-crypto`.
- [ ] Run the OpenSSL example validation script.
- [ ] Inspect the final diff and dependency feature graph.
- [ ] Run `git diff --check` and report any environment-limited checks precisely.
