# PR #16 Review — Changes Made

## Summary

The PR (`docs/beta-launch-readme`) promoted OpenShell's status from alpha to
beta in the README badge and callout heading, but left three other user-facing
surfaces out of sync. The review identified all three gaps; this commit
addresses them.

---

## Change 1 — `README.md` line 13: fix contradictory callout heading

### Problem
The PR changed the callout heading to **"Beta software — single-player and
multiplayer mode"**, but the very next sentence reads *"one developer, one
environment, one gateway. We are **building toward** multi-tenant enterprise
deployments"*. Claiming multiplayer is available now directly contradicts the
aspirational framing of the body.

### Fix
Changed heading to **"Beta software — expanding toward multiplayer mode"**.
This is honest: beta status is confirmed, single-player scope is the current
reality, and multi-tenant is acknowledged as the direction — not a fait
accompli.

---

## Change 2 — `fern/docs.yml` line 16: update docs-site announcement banner

### Problem
The site-wide banner at `docs.nvidia.com/openshell` still read:
> 🔔 NVIDIA OpenShell is **alpha software**. APIs and behavior may change
> without notice. **Do not use in production.**

Every visitor to the docs site would see "alpha" while the README now says
"beta", creating inconsistent messaging. The hard "Do not use in production"
warning is also stricter than appropriate for beta.

### Fix
Updated the banner to:
> 🔔 NVIDIA OpenShell is **beta software**. APIs and behavior may change
> without notice. **Use in production at your own risk.**

"Beta software" aligns with the README. The production warning is softened to
reflect that beta software *can* be used in production — with appropriate
caution — rather than being categorically prohibited.

---

## Change 3 — `pyproject.toml` line 23: bump PyPI development-status classifier

### Problem
The published `openshell` package retained the trove classifier:
```
Development Status :: 3 - Alpha
```
PyPI surfaces this in the package sidebar. Users discovering the package via
PyPI would see "Alpha" while the README badge and callout now say "Beta".

### Fix
Bumped to:
```
Development Status :: 4 - Beta
```
This keeps the PyPI metadata consistent with all other user-facing status
indicators.

---

## Commit

```
docs(beta): align all beta status references across user-facing surfaces
```

Branch: `docs/beta-launch-readme`  
Commit: `f41668a0`  
Signed-off-by: OpenShell Agent <agent@openshell.dev>
