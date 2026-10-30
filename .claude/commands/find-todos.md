---
description: List all TODO and FIXME comments, grouped by file
---

Find every TODO and FIXME comment in this codebase.

Rules:
- Ignore the .claude folder, node_modules, .git, dist, build, and any vendored or generated files.
- Group results by file path, with files sorted alphabetically.
- Within each file, sort items by line number.
- For each item show: line number, TODO or FIXME, and the comment text.
- End with a total count, like "12 TODOs, 3 FIXMEs across 5 files."
- If nothing is found, just say "No TODOs or FIXMEs found."

Output only the list. No extra commentary.