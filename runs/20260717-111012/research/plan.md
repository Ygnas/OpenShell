**Implementation Plan – /tmp/plan.md**

```markdown
# Issue #2332 – docs(vm): clarify MicroVM driver use cases and limitations

## Issue Summary
The MicroVM compute driver is inconsistently described across the repository:
- `docs/reference/sandbox-compute-drivers.mdx` calls it a VM‑boundary tool.
- `architecture/compute-runtimes.md` and the driver README label it *experimental*.
- `docs/reference/support-matrix.mdx` lists it as *supported* without qualification.
- No single place lists the driver’s intended use, maturity, or known limitations.

This ambiguity makes it hard for users to decide whether the driver is suitable for production or only for experimentation.

## Approach
1. **Create a single, authoritative description** of the MicroVM driver in `docs/reference/sandbox-compute-drivers.mdx`.  
   * Add a concise “Limitations” subsection that covers:  
     - Experimental maturity & production‑readiness.  
     - Intended use (VM‑isolation experiments, local alternative when Docker/Podman are unavailable).  
     - Host virtualization requirement & supported platforms.  
     - Any other known constraints (e.g., Linux‑only, limited feature set).  
   * Add a “Maturity” tag (e.g., `⚠️ Experimental`) so the status is immediately visible.

2. **Propagate the same language** to the other documentation touchpoints:  
   * `docs/reference/support-matrix.mdx` – mark MicroVM as *Supported (Experimental)* or *Experimental* and link to the detailed section in `sandbox-compute-drivers.mdx`.  
   * `architecture/compute-runtimes.md` – update the MicroVM entry to reflect its experimental status and add a note about its intended use.  
   * `crates/openshell-driver-vm/README.md` – update the “Maturity” section, add a “Use Cases” paragraph, and list the same limitations.

3. **Search‑and‑replace** any other occurrences of “MicroVM” in docs that might still refer to it as fully supported or omit the experimental label.  
   * Use a repo‑wide grep to find all references and update them accordingly.

4. **Validate links & formatting** after changes.  
   * Run `mdlint` (or the repo’s markdown linter) to catch broken links or syntax errors.  
   * Ensure that the new sections are properly anchored for cross‑references.

5. **Commit & PR**  
   * Create a single PR that contains all the above changes.  
   * Add a clear commit message and link to the issue.  
   * Request review from the docs team and the driver maintainers.

## Files to Modify

| File | What to Change | Why |
|------|----------------|-----|
| `docs/reference/sandbox-compute-drivers.mdx` | Add a **Limitations** subsection; add a **Maturity** tag; update wording to emphasize experimental nature and intended use. | Central, authoritative description. |
| `docs/reference/support-matrix.mdx` | Update MicroVM row to “Supported (Experimental)” or “Experimental”; add a note linking to the detailed section. | Align support matrix with reality. |
| `architecture/compute-runtimes.md` | Update MicroVM entry: change status to *Experimental*, add a brief note on intended use. | Consistency across architecture docs. |
| `crates/openshell-driver-vm/README.md` | Update “Maturity” section to *Experimental*; add “Use Cases” paragraph; list limitations. | Driver README must reflect same information. |
| **Optional**: any other docs containing “MicroVM” | Ensure they reference the new maturity status and limitations. | Avoid lingering inconsistencies. |

## Considerations & Edge Cases

| Consideration | Impact | Mitigation |
|---------------|--------|------------|
| **Existing links** | Some docs may link directly to the MicroVM section; ensure anchors remain valid after adding new subsections. | Use stable anchors (`#limitations`) and update any broken links. |
| **Search‑and‑replace** | Risk of unintentionally changing unrelated text. | Use precise search patterns (`MicroVM` with surrounding context) and review each change. |
| **Future updates** | The driver may evolve; documentation should be easy to update. | Keep the new sections modular and reference a single source of truth (the sandbox‑compute‑drivers page). |
| **CI / linting** | New markdown may break linters or CI checks. | Run `mdlint` locally before pushing; fix any reported issues. |
| **Audience** | Some users may still rely on the driver for production workloads. | Clearly state “Not recommended for production” in the maturity section. |
| **Platform support** | The driver may support more platforms in the future. | Document current supported platforms and note that the list may change. |

## Deliverables

1. Updated `sandbox-compute-drivers.mdx` with a new **Limitations** section and maturity tag.  
2. Updated `support-matrix.mdx`, `compute-runtimes.md`, and `openshell-driver-vm/README.md` to reflect the same status.  
3. Repository‑wide search to ensure no contradictory statements remain.  
4. PR with clear commit messages and issue reference.

---

**Next Steps**  
- Create the PR following the plan above.  
- Request review from the docs and driver teams.  
- Once merged, monitor for any downstream issues or user feedback regarding the updated documentation.