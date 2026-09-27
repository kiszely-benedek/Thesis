"""The Q&A system and its evaluation (design `qa-system.md`).

This package holds the system under test — the retrieval strategies that
answer questions about a plant graph — and the yardstick it is measured
against: questions with a computable reference answer, generated from the
same ground-truth graph the strategies never get to see directly.

`models.py` holds the shared data model (questions, answers, outcomes,
results, run and corpus records — no logic). `scoring.py` compares a
strategy's answer to the reference answer with plain, dependency-free
Python: no network call and no database read is ever needed to know whether
an answer was right (ADR-0013).
"""

from __future__ import annotations
