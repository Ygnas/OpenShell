# Opt-in OpenSSL Crypto Backend Design

## Goal

Add an opt-in system-OpenSSL crypto backend for regulated-build experimentation
while preserving AWS-LC as the default backend for upstream OpenShell builds.

## Requirements

- Normal builds continue to select AWS-LC without requiring system OpenSSL.
- A dedicated OpenSSL feature/build selection activates the OpenSSL backend.
- AWS-LC and OpenSSL backend features are mutually exclusive at compile time.
- The OpenSSL selection must not silently retain AWS-LC through Rustls, rcgen,
  JWT, tonic, hyper-rustls, kube, or SQLx feature paths.
- Both backends implement the existing `CryptoBackend` and `ProtocolBackend`
  contracts, including primitives, PKI, JWT, and Rustls provider construction.
- Existing credential envelope bytes and persisted key encodings remain
  compatible.
- Contract tests cover both backends; OpenSSL tests additionally verify the
  linked/provider version and an actual Rustls handshake.
- Backend selection is not itself a FIPS claim. Strict host FIPS/provider
  attestation remains a separate follow-up gate.

## Design

`openshell-crypto` will expose mutually exclusive `aws-lc` and `openssl`
features. AWS-LC remains the default. The OpenSSL implementation will move from
the isolated proof-of-concept into the crate as a backend module, using the
system OpenSSL and the OpenSSL-backed Rustls provider already exercised by the
POC. The façade and application call sites remain backend-neutral.

The first implementation slice provides an explicit opt-in path for the
`openshell-crypto` crate and its isolated contract harness. The ordinary
upstream workspace build path remains AWS-LC. Product-wide propagation to the
gateway and supervisor dependency graph is a follow-up packaging step because
Cargo feature selection must be threaded through the internal crate graph;
dependency-owned TLS integrations must be checked before that path is enabled.

The implementation will retain the current capability model and report the
OpenSSL provider version, but it will not mark the backend as FIPS-verified.
RHEL/UBI image construction, validated-module identification, host FIPS mode,
and fail-closed startup behavior are outside this first implementation slice.

## Compatibility and risks

- The OpenSSL-backed Rustls provider is an external/provider dependency and may
  require system OpenSSL 3 headers and shared libraries.
- `jsonwebtoken`, `rcgen`, and Rustls must all use compatible OpenSSL-backed
  adapters; no fallback to AWS-LC is permitted in the OpenSSL build.
- SSH/russh and other dependency-owned crypto remain outside this slice unless
  the existing call graph proves they already route through the façade.
- The current workspace dependency declarations may require product-level
  feature forwarding rather than only changing `openshell-crypto`.

## Verification

- Compile and test the default AWS-LC backend.
- Compile and test the OpenSSL backend with explicit system OpenSSL settings.
- Run dependency-tree/source checks sufficient to demonstrate that the
  OpenSSL build does not retain AWS-LC in the selected crypto paths.
- Preserve the existing POC as a reference until production backend tests
  cover all behavior it currently exercises.

## CI

Add a FIPS-oriented workflow that is safe to run from pull requests in the
upstream repository and in forks. The pull-request path will build the OpenSSL
feature set in a UBI 9 builder, run the focused tests and dependency report,
build a local FIPS image, and run the image scanner without requiring secrets
or publishing permissions. A manual or protected-branch path may additionally
verify Red Hat image signatures, push a `-fips` artifact, and run against a
FIPS-enabled RHEL/RHCOS runner where available.

The workflow must use `pull_request` for untrusted code and must not expose
registry, signing, or release secrets to forked pull requests. It should be
usable with `workflow_dispatch` on both the upstream repository and a fork,
with publish steps either omitted or gated behind trusted refs and explicit
permissions. A hosted Ubuntu runner can validate the build and local scan;
runtime FIPS-mode evidence requires a separately provisioned FIPS-capable
environment and must not be represented by the hosted build job alone.
