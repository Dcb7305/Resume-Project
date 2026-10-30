---
name: push-to-github
description: Use when I say "push my changes", "save my work to GitHub", "commit and push", or "get this onto GitHub" in my Resume Project or course repos.
---

# Push my changes to GitHub

Follow these steps in order. Stop and tell me if anything looks wrong instead of guessing.

1. **Check where I am.** Run `git status` and `git branch --show-current`. Tell me the branch name and list the changed, new, and deleted files in plain English.

2. **Show me what changed.** Run `git diff --stat`, then summarize each file's changes in one line. Flag anything that looks accidental: data files I didn't mean to touch, credentials or keys, `.env` files, or huge files.

3. **Stage only the right files.** Use `git add <file>` for each file that belongs in this commit. Don't use `git add .` unless I say so. Leave out anything flagged in step 2 until I confirm.

4. **Write the commit message.** Suggest a short message in the format `verb: what changed` (for example `add: validation checks for Answer Rate`). Keep it under 60 characters. Wait for me to OK or tweak it, then run `git commit -m "<message>"`.

5. **Sync before pushing.** Run `git pull --rebase`. If there's a merge conflict, stop, show me the conflicting files, and explain the conflict before changing anything.

6. **Push.** Run `git push`. If the branch has no upstream yet, use `git push -u origin <branch>`.

7. **Confirm it landed.** Run `git log -1 --oneline` and `git status`, then tell me the commit hash and that the working tree is clean. If this is a course task, remind me to open a pull request on GitHub so the platform can detect it.