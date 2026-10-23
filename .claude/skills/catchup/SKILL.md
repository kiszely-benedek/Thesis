---
name: catchup
description: Load project context at the start of a new chat. Reads the index, recent progress, open decisions and git log so a fresh session knows where the dissertation stands without re-scanning the repo. Run this first in any new conversation.
---

# Catch up on project state

Read these in order and stop. Do not explore the repo beyond this list — the point is a cheap, deterministic bootstrap, not a survey.

1. `docs/private/00-index.md` — the map.
2. The **three most recent** files in `docs/private/50-progress/` (sort by filename, they are date-ordered).
3. All files in `docs/private/20-decisions/` whose frontmatter says `status: proposed` or `status: accepted`. Skip `superseded`.
4. `docs/private/30-experiments/_results.md` if it exists — the running results table.
5. `git log --oneline -20` and `git status --short`.

## Then report, in this shape

- **Where we are** — one paragraph. Current phase, what was last finished.
- **Open decisions** — any ADR still `proposed`, with the question it is blocking.
- **In flight** — uncommitted changes, unfinished work visible in progress notes.
- **Next action** — the single most useful thing to do now, and why.

Keep the whole report under ~30 lines. If something in the index contradicts what git shows, say so explicitly — that means the documentation drifted and needs fixing before anything else.
