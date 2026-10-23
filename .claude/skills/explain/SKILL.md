---
name: explain
description: Research a topic the user wants to learn and write a teaching note into docs/Notes/. Any software engineering topic — not only dissertation ones. Concepts, standards, tools, languages, architecture, algorithms, testing, infra, whatever comes up.
---

# Write a teaching note

Argument: the topic. Output: one file at `docs/Notes/<topic-slug>.md`.

The reader is a competent master's student who has not met this topic before and wants to genuinely learn it — not skim it. Write to teach.

**Scope is all of software engineering.** RDF and DEXPI, yes, but equally: async Python, database indexing, Docker, CAP theorem, dependency injection, memory management, CI pipelines, type systems. If the user asks, write it. Do not steer everything back to P&IDs.

## Rules

- **Write the note in Hungarian.** Headings, prose and examples in Hungarian; identifiers, code, tags and quoted drawing text stay as printed. The frontmatter keys stay English. (User decision, 2026-09-05 — the notes are the user's own study material.) The interview questions at the end of the reply follow the language of the conversation.
- **Lead with the problem the thing solves**, before any syntax or definition. Someone who does not know why a technology exists cannot remember what its parts are called.
- **Ground it in a real example.** Prefer this project when the topic genuinely touches it, since concrete beats abstract — but a general topic gets a general example. Never force a P&ID metaphor onto something unrelated; a bad analogy teaches worse than none.
- **One worked example** with real, runnable detail.
- **Say where it fits, or that it does not.** If we use it here, link the ADR. If we do not, say so plainly — knowing why something was rejected is worth as much as knowing how it works.
- **Flag the misconceptions** newcomers reliably have.
- Verify against current sources. Never write from memory about library APIs, versions or standards.

## Structure

```markdown
---
topic: <name>
status: draft | reviewed
related: [<ADRs, other notes>]
---

# <Topic>

## Why it exists
## The core idea
## Worked example
## Where it fits (or does not)
## Common misconceptions
## If you read one thing
<a single best link, not a bibliography>
```

One to two pages. Long enough to teach, short enough to read in a sitting.

## Then quiz them — as an interviewer, not a teacher

Finish your reply with **3–5 questions in the style of a real technical interview**, not a school exam. That means:

- **No definition recall.** "What is an index?" is a teacher's question. "This query got slow after the table hit 10M rows — walk me through how you'd diagnose it" is an interviewer's.
- **Scenario- and tradeoff-driven.** Put them in a situation and make them choose, then justify. Good interview questions have more than one defensible answer.
- **Escalating.** Start where they should be comfortable, end somewhere they will probably struggle. The last question is meant to find the edge of their understanding, not to be answered cleanly.
- **Follow-up ready.** Note briefly what you would push back on for each — the real signal in an interview comes from the second and third question, not the first.
- **Include the one that catches people out.** Every topic has a question where the confident answer is wrong.

Offer to run it as an actual mock interview if they want to answer out loud rather than just read the questions.
