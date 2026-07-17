# PR #16 Review — docs(readme): update README for beta launch

## Summary

The diff is a 2-line documentation-only change to `README.md`:
- Badge URL: `status-alpha-orange` → `status-beta-orange`
- Callout heading: "Alpha software — single-player mode." → "Beta software — single-player and multiplayer mode."

Both modified lines are mechanically correct. No code is touched; no callers are broken.

## Findings

### 1. [INLINE] README.md line 13 — Self-contradicting callout body
**What's wrong:** The new heading claims "single-player and **multiplayer** mode" but the sentence that immediately follows still reads "one developer, one environment, one gateway. We are *building toward* multi-tenant enterprise deployments" — directly contradicting the headline claim that multiplayer is already available.

**Failure scenario:** A prospective user reads "multiplayer mode" in the heading, then reads the body which says the project is still a single-gateway proof-of-concept that is only *building toward* multi-tenancy — causing confusion about what is actually shipping in beta.

**Fix:** Either update the body text to describe the multiplayer capability that now exists, or soften the heading to "expanding toward multiplayer mode" to match the aspirational framing of the body.

---

### 2. [REVIEW BODY] `fern/docs.yml` line 16 — Docs-site banner still says "alpha software"
**What's wrong:** `fern/docs.yml` line 16 contains the site-wide announcement banner:
```
🔔 NVIDIA OpenShell is <strong>alpha software</strong>. APIs and behavior may change without notice. Do not use in production.
```
This banner is shown on every page of `docs.nvidia.com/openshell` and is outside the diff.

**Failure scenario:** Every visitor to the official documentation site sees "alpha software" while the README now advertises "beta", creating contradictory messaging at the most visible entry point for new users.

**Fix:** Update the banner to reflect beta status; also consider whether "Do not use in production" still applies given the beta promotion.

---

### 3. [REVIEW BODY] `pyproject.toml` line 23 — PyPI classifier still `Development Status :: 3 - Alpha`
**What's wrong:** The PyPI package classifiers still include `"Development Status :: 3 - Alpha"`.

**Failure scenario:** Developers browsing or `pip install`-ing the `openshell` package on PyPI see "Alpha" in the package metadata while the README badge and callout say "Beta", creating inconsistent messaging across distribution channels.

**Fix:** Change the classifier to `"Development Status :: 4 - Beta"`.

---

## Verdict

**COMMENT (not approved).** The diff itself is correct but the beta promotion is incomplete. At minimum, the contradictory body text on line 13 should be resolved before merging, and `fern/docs.yml` + `pyproject.toml` should be updated in the same PR for consistency.
