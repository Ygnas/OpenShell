# PR #17 Review — docs: update README for beta launch

## Summary

The two changes in `README.md` are correct as written. The badge URL and
blockquote text both accurately reflect the beta promotion.

## Finding — Missed update in `fern/docs.yml`

**File:** `fern/docs.yml`, line 7 (outside the diff)

The `fern/docs.yml` file contains a site-wide announcement banner:

```yaml
announcement:
  message: "🔔 NVIDIA OpenShell is <strong>alpha software</strong>. APIs and behavior may change without notice. Do not use in production."
```

This will continue to display "alpha software" to all visitors of the
documentation site after this PR merges, directly contradicting the
`README.md` badge and blockquote that this PR promotes to beta.

The PR description states that a `grep` sweep "of all Markdown files"
confirmed no other files reference the project's alpha status, but
`fern/docs.yml` is a YAML file and was not in scope for that sweep.

**Fix:** Update `fern/docs.yml` line 7 to reflect beta status (or remove
the announcement banner entirely if the "do not use in production" warning
is no longer appropriate).

## Verdict

COMMENT — one missed file keeps the docs-site banner at "alpha software".
No correctness bugs in the lines that were changed.
