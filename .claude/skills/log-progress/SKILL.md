---
name: log-progress
description: Append what happened this session to the weekly progress log so a future chat can resume without re-deriving context. Run at the end of a working session, or before context runs out.
---

# Log progress

Write to `docs/private/50-progress/<YYYY>-W<week>.md`, creating it if the week is new. **Append** a dated entry — never rewrite earlier entries.

## Entry format

```markdown
## <YYYY-MM-DD>

**Done**
- <what actually changed — files, decisions, results>

**Findings**
- <anything learned that is not obvious from the diff: a number, a dead end, a surprise>

**Open**
- <unresolved questions, blocked items>

**Next**
- <the concrete next action>
```

## Rules

- Record **dead ends and negative results**. "Tried X, it failed because Y" saves a future session from repeating it and is worth more than a list of successes.
- Reference real artifacts: file paths, commit hashes, ADR numbers, experiment IDs.
- Quote actual numbers from actual runs. Never write a result that was not measured.
- If an ADR was decided, or an experiment produced a number, make sure it also landed in `20-decisions/` or `30-experiments/` — the progress log points at those, it does not replace them.
- Keep it short. This is a resumption aid, not a diary.

Then check whether `docs/private/00-index.md` still describes reality (current phase, next milestone). If it drifted, update it.

## Update the status page — every time

Finally, bring **`docs/private/ALLAPOT.md`** up to date (added 2026-09-27 at the user's request). It is the user's one-glance
status page, **written in Hungarian**, and it must never be stale after a session. Update, in place:

1. The **"Frissítve"** date.
2. **"Egy mondatban"** — one sentence on where things stand.
3. **Fázisok** and the **Feladatok** tables — every task's status (✔ / 🟡 folyamatban / ⬜ / ✖ elvetve), with the
   **commit hash and date** for finished ones (from `git log`, never from memory). Only mark ✔ what is committed.
4. **Ellenőrzőpontok** — each checkpoint against its calendar date: 🟢 ahead, 🟡 on track, 🔴 behind — say why in a
   few words.
5. **Mi vár rád** — every decision, commit, approval or link the user owes, most urgent first.
6. **Mit olvass el legközelebb** — at most four items, most useful first.

Rules for this page: plain Hungarian, short; no number that is not in `_results.md`, `git log` or a file; never name
any person other than the user and the professor; out-of-scope items are flagged as "nem része ennek a munkának".
