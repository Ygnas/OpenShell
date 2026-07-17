# PR #15 Review — docs(readme): update README to reflect beta status

## Summary

The PR updates two places in `README.md` to reflect the project's promotion from alpha to beta:
1. The shields.io badge URL (`status-alpha-orange` → `status-beta-orange`)
2. The blockquote callout (alpha wording → beta wording with multi-tenant context)

Both changes within the diff are internally consistent and accurate.

## Findings

### Finding 1 — `fern/docs.yml` line 16: Docs-site banner still says "alpha software"

**What is wrong:** The announcement banner displayed sitewide on `docs.nvidia.com/openshell` reads:
```
"🔔 NVIDIA OpenShell is <strong>alpha software</strong>. APIs and behavior may change without notice. Do not use in production."
```
This directly contradicts the updated README badge and callout that now say *beta*.

**Failure scenario:** Every visitor to the OpenShell documentation site sees a prominent "alpha software" banner, contradicting the README's "beta" status.

**Fix:** Update `fern/docs.yml` line 16 to read `beta software` and revisit the "Do not use in production" restriction if beta implies greater stability.

---

### Finding 2 — `pyproject.toml` line 23: PyPI classifier still set to Alpha

**What is wrong:** The package classifier is:
```
"Development Status :: 3 - Alpha",
```
This is the classifier surfaced on the PyPI package page and used by tools that filter packages by maturity.

**Failure scenario:** Developers browsing the `openshell` package on PyPI see "Alpha" status while the README says "beta", creating mixed messaging.

**Fix:** Change to `"Development Status :: 4 - Beta"`.

---

## Verdict

**COMMENT (not approved).** The diff itself is correct, but the change is incomplete — two other user-facing surfaces (`fern/docs.yml` and `pyproject.toml`) still advertise alpha status and should be updated in the same PR for consistency.
