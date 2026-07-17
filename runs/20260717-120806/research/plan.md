**/tmp/plan.md**

```markdown
# Issue #14 – Update README for Beta Launch

## Issue
The repository’s `README.md` still references OpenShell as *alpha* software.  
Two places need updating:

1. The status badge (line 7) – `status-alpha-orange` → `status-beta-orange`.
2. The callout block (line 13) – “Alpha software — single-player mode.” → a new
   beta‑status message that also mentions the expanded scope.

## Approach
1. **Locate the badge**  
   Find the Markdown image link on line 7:
   ```markdown
   [![Project Status](https://img.shields.io/badge/status-alpha-orange)](...)
   ```
   Replace `status-alpha-orange` with `status-beta-orange`.  
   The surrounding link (`(...)`) is a placeholder and can stay unchanged.

2. **Rewrite the callout block**  
   Find the blockquote on line 13:
   ```markdown
   > **Alpha software — single-player mode.**...
   ```
   Update the text to reflect the beta status and expanded scope.  
   A suitable rewrite is:
   ```markdown
   > **Beta software — single-player mode and multi‑player mode.**...
   ```
   (Feel free to adjust the expanded scope wording if the project’s scope is
   different; the key is to remove “Alpha” and mention the new features.)

3. **Verify formatting**  
   - Ensure the badge still renders correctly on GitHub.  
   - Confirm the blockquote still appears as a callout (bold text inside a
     blockquote).  
   - Run a quick preview (`git preview` or `open README.md` in a browser) to
     confirm visual correctness.

4. **Commit**  
   - Add a clear commit message:  
     `docs: update README to reflect beta status`  
   - Push to the main branch and open a PR if required.

## Files
- **`README.md`**  
  *Modify* the badge line and the callout block as described above.

## Considerations
- **Badge URL** – The link after the image is a placeholder (`(...)`).  
  If the repository has a real URL for the status badge, keep it unchanged.
- **Expanded scope wording** – The issue states “expanded scope” but does not
  specify the new features. Use a generic expansion (e.g., adding multi‑player
  mode) or replace with the correct feature set once clarified.
- **Other docs** – No other files reference “alpha” status per the issue
  description. If additional references exist in the future, they should be
  updated similarly.
- **CI / Lint** – After editing, run any Markdown linting or CI checks to
  ensure no style violations were introduced.

--- 

**End of plan.**