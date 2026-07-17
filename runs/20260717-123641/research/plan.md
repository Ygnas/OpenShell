**/tmp/plan.md**

```markdown
# Issue #14 – Update README for Beta Launch

## Issue
The repository README still references OpenShell as *alpha* software.  
Specifically:

1. The status badge uses `status-alpha-orange`.  
2. A callout block reads:  
   > **Alpha software — single-player mode.**

These need to be updated to reflect the new *beta* status and the expanded scope of the project.

## Approach
1. **Badge Update**  
   * Replace `status-alpha-orange` with `status-beta-orange` in the badge URL.  
   * Keep the surrounding Markdown unchanged (`[![Project Status](…)](…)`).

2. **Callout Block Rewrite**  
   * Change the text to reflect beta status and the expanded scope.  
   * Suggested wording:  
     ```markdown
     > **Beta software — single-player and multiplayer mode.**
     ```  
     (Feel free to adjust the wording to match the project’s official description.)

3. **Verify Badge Link**  
   * Ensure the badge still points to the correct repository or status page.  
   * No change to the link target is required unless the project’s status page URL has changed.

4. **Commit & Test**  
   * Run `git diff` to confirm only the intended lines changed.  
   * Push the change and verify the badge renders correctly on GitHub.

## Files
| File | Change |
|------|--------|
| `README.md` | - Line 7: Update badge URL from `status-alpha-orange` to `status-beta-orange`. <br> - Line 13: Rewrite callout block to: `> **Beta software — single-player and multiplayer mode.**` |

> **Note**: If the README contains additional “Alpha” references outside these two lines, they should be reviewed and updated accordingly, but the issue only requires the two changes above.

## Considerations
- **Badge Color**: The new badge uses `status-beta-orange`. If the project prefers a different color for beta, adjust the color segment accordingly (e.g., `status-beta-blue`).  
- **Scope Expansion**: The callout now mentions multiplayer mode. If the project also supports co‑op or other modes, include them in the wording.  
- **Documentation Consistency**: After updating the README, run a quick search for the word “Alpha” in the repository to ensure no other references remain.  
- **CI/CD**: No build or test changes are required; this is purely a documentation update.  

--- 

**Next Steps**  
1. Apply the changes to `README.md`.  
2. Commit with a clear message, e.g., “docs: update README for beta launch.”  
3. Push to the main branch and verify the badge and callout render correctly on GitHub.  
4. Close the issue once the PR is merged.  

```