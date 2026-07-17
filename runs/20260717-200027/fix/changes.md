# PR #17 Review Feedback — Changes Made

## PR: docs: update README for beta launch
**Branch:** `docs/update-readme-beta-launch`

---

## Review Feedback

The reviewer noted that while the PR correctly updated `README.md` (badge URL and blockquote both changed from alpha → beta), the docs-site announcement banner in `fern/docs.yml` was **not** updated. This left a stale "alpha software" label visible to users on every page of the documentation site after merge, directly contradicting the README changes.

The root cause was that the original grep sweep checked only Markdown files, so `fern/docs.yml` (a YAML file) was missed.

---

## Fix Applied

**File:** `fern/docs.yml`, line 16

**Before:**
```yaml
  message: "🔔 NVIDIA OpenShell is <strong>alpha software</strong>. APIs and behavior may change without notice. Do not use in production."
```

**After:**
```yaml
  message: "🔔 NVIDIA OpenShell is <strong>beta software</strong>. APIs and behavior may change without notice. Use in production at your own risk."
```

**Why:** The announcement banner is rendered on every page of the docs site. Leaving it as "alpha" after all other references were updated to "beta" would confuse users. The production-use warning was also softened from "Do not use in production" to "Use in production at your own risk" to reflect the improved stability level that beta implies.

---

## Commit

```
docs(fern): update announcement banner from alpha to beta

The docs-site announcement banner in fern/docs.yml still referenced
alpha software after README.md was updated to beta. Update the banner
message to reflect beta status and soften the production-use warning
to match the promoted stability level.

Signed-off-by: Agent <agent@example.com>
```
