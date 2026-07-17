**/tmp/plan.md**

```markdown
# Issue #14 – Update README for Beta Launch

## Issue
The repository README still references OpenShell as *alpha* software in two places:
1. The status badge (`status-alpha-orange`).
2. The call‑out block that reads “Alpha software — single‑player mode.”

With the upcoming beta release these references must be updated to reflect the new status and expanded scope.

## Approach
1. **Badge Update**  
   * Locate the badge image URL in the README header (line ~7).  
   * Replace `status-alpha-orange` with `status-beta-orange`.  
   * Keep the surrounding Markdown link unchanged (it points to the repo or status page).

2. **Call‑out Block Rewrite**  
   * Find the blockquote that starts with `> **Alpha software — single-player mode.**`.  
   * Rewrite it to describe the beta status and the expanded scope.  
   * Suggested wording:  
     ```markdown
     > **Beta software — single‑player mode and multiplayer support.**  
     > OpenShell now offers a richer experience with new features and improved stability.
     ```  
   * Ensure the blockquote remains a single paragraph or split into two if needed for readability.

3. **Verification**  
   * Run `git diff` to confirm only the two targeted changes.  
   * Render the README locally (e.g., `mdpreview README.md` or GitHub preview) to verify the badge displays correctly and the call‑out block looks as intended.

4. **Commit & PR**  
   * Commit the changes with a clear message: “docs: update README for beta launch”.  
   * Push to a new branch and open a PR for review.

## Files
| File | Change |
|------|--------|
| `README.md` | • Replace badge URL `status-alpha-orange` → `status-beta-orange`. <br>• Rewrite the call‑out block from “Alpha software — single‑player mode.” to the new beta description. |

## Considerations
- **Badge Color**: The current badge uses orange. If the project’s style guide prefers a different color for beta (e.g., blue), adjust accordingly.  
- **Link Target**: The badge link currently points to the repository or a status page. Verify that the link remains valid after the URL change.  
- **Scope Expansion**: The issue mentions “expanded scope.” If the project has additional features (e.g., multiplayer, new UI), mention them briefly in the call‑out block.  
- **Consistency**: Ensure no other files (e.g., `docs/`, `CONTRIBUTING.md`) still reference “alpha.” A quick grep can confirm.  
- **CI Rendering**: If the project uses CI to render the README (e.g., GitHub Actions), run the pipeline to catch any Markdown syntax errors.  

---  

**Next Steps**  
1. Edit `README.md` as described.  
2. Commit and push.  
3. Open PR and await review.  

```