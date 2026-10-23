# Dissertation — GraphRAG at plant scale for P&ID engineering diagrams

## What this is

A BSc thesis (BME VIK mérnökinformatikus, TMIT szakdolgozat; **in Hungarian** (user, 2026-10-05)) testing one claim:

> The optimal retrieval strategy for GraphRAG over engineering diagrams is a **function of corpus scale**. The published optimum — serializing a condensed single-sheet graph into the prompt (ChatP&ID, 0.91 accuracy) — is an artifact of single-page evaluation and inverts at plant scale.

Scope: from one ~100-page scanned factory document, to a whole plant region of ~10 such documents.

## Start here

**Run `/catchup` at the start of every session.** It reads `docs/private/00-index.md`, recent progress, open ADRs and the git log, and tells you where things stand. Do not scan the repo manually instead — that costs 20× the tokens for the same answer.

## Working rules

- **Design before code.** Non-trivial components go through the `architect` agent → a design note in `docs/private/40-design/` → then the `coder` agent.
- **Decisions become ADRs.** Anything with a real alternative gets a numbered ADR in `docs/private/20-decisions/`. The professor reviews pull requests and will ask "why this way".
- **Code is read by a professor, not a compiler.** Small functions, type hints, docstrings, max two levels of nesting, no stacked loops. See `.claude/agents/coder.md`.
- **Never invent a number.** Every figure in a note or a reply must come from a run that happened or a paper that was read. Cite the source.
- **Log before context runs out.** `/log-progress` at the end of a session.
- **The chat is the user's single source of truth (user, 2026-10-03).** The user reads only what is written in
  the chat — never ADRs, design notes, results files or reports. Every decision (what, why, the alternatives),
  every result (the numbers, what they mean, their caveats) and every question the user must answer goes into the
  chat, in Hungarian, in plain words, with tables where useful. Files under `docs/` stay the durable record for
  traceability and the thesis, but they are never a substitute for saying it in the chat. Never answer "see ADR-X"
  or "read §Y" — summarize X and Y in the chat instead.

### Hard rules — no exceptions

- **Never commit, never push. Ever.** Not `git commit`, not `git push`, not `git merge`, not
  `git rebase`, not `git tag`, not a PR, not `--amend`, not "just this once", not when the user
  says "commit this" — in that case you still stop and hand them the command. Staging
  (`git add`) counts as commit preparation and is also the user's. When work is ready, print the
  exact command and the full commit message in the chat, in a copyable block, and stop there.
  The user runs it. Read-only git (`status`, `log`, `diff`, `show`, `grep`) is always fine.
  **Rationale:** the user reviews every change before it enters history, and the published
  history must stay under their control (see the 2026-09-19 history rewrite).
- **Commit messages carry no attribution trailer** and no mention of the tooling used to write
  the code. No `Co-Authored-By`, no "Generated with", no model names.
- **Use the repo's own skills when they apply.** `/catchup` starts every session, `/log-progress`
  ends it, `/paper-intake` files any new paper, `/explain` writes a teaching note, `/lit-gap-check`
  is the fortnightly novelty watch, `python-comments` audits or writes comments. Do not hand-roll
  what a skill already does. Proposing a *new* skill is welcome — describe what it would do and
  why the existing ones do not cover it, and let the user decide before building it.

## Tooling

Pydantic (data model) · pyDEXPI (DEXPI conversion, **AGPL-3.0** — see ADR-0003) · Neo4j LPG only — the RDF arm is not built (ADR-0012 K3, superseding ADR-0002 in part) · PID2Graph (Zenodo 14803338 — validates digitization, **not** scale)

## Agents and skills

| | |
|---|---|
| `architect` | designs and ADRs, no production code |
| `coder` | implements an agreed design, readable style |
| `researcher` | papers, novelty checks, technology investigation |
| `/catchup` | session bootstrap |
| `/paper-intake <id>` | read a paper properly, file a structured note |
| `/lit-gap-check` | novelty watch — scheduled fortnightly |
| `/explain <topic>` | teaching note into `docs/Notes/` |
| `/log-progress` | append to the weekly log |
| `python-comments` | write or audit comments against the 9-type taxonomy |

**Model assignment (ADR-0006, amended 2026-09-25):** planning and ADRs on **the latest available Opus** — currently **Opus 5.5**, at **high** reasoning effort for planning; on **Fable 5.1** only when the user asks for it on that task; implementation (`coder`) always on **Sonnet**. Coders run one at a time, never in parallel. The rule names "latest Opus" rather than a fixed version so it does not go stale as models ship.

**Teaching notes:** the user is new to P&IDs and to research. Whenever a step needs a concept they have not met, write a Hungarian note into `docs/Notes/` without being asked — more explanation is better than less (user request, 2026-09-06).
