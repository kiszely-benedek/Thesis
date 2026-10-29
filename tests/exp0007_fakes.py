"""Fake stored inputs of the R4 / R5 tests: validation runs, questions, prompt sizes, E1 runs.

Costs are chosen so every mean is exact; nothing here is a measured number.
"""

from __future__ import annotations

import json
from pathlib import Path

#: dollars per question written into the fake validation runs
V7_COSTS = {
    "V7-CYP-A-X100g2s212": 0.0007,
    "V7-AG-X100g2s212": 0.0014,
    "V7-CYP-A-X1000g2s213": 0.0006,
    "V7-AG-X1000g2s213": 0.0013,
    "V7F1-CYP-X100g2s212": 0.0005,
    "V7F1-AG-X100g2s212": 0.0008,
    "V7F1-CYP-X1000g2s213": 0.0004,
    "V7F1-AG-X1000g2s213": 0.0009,
}
#: estimated prompt tokens of the small ladder corpora in the fake prompt_size.json
PROMPT_TOKENS = {"H1g2": 20_000, "H3g2": 40_000, "H10g2": 160_000, "H30g2": 480_000}
#: completion tokens per question of the fake EXP-0001 ContextRAG-high runs
E1_COMPLETION = {"H1": 200, "H3": 600, "H10": 1200}


def write_cost_run(root: Path, name: str, usd: float) -> None:
    """A two-question run costing `usd` each: one in the final call, one in retrieval."""
    run = root / name
    run.mkdir(parents=True)
    rows = [
        {"question_id": "C:CONNECTED:a", "cost_usd": usd},
        {"question_id": "C:CONNECTED:b", "retrieval_usage": {"cost_usd": usd}},
    ]
    (run / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def write_v7_runs(root: Path) -> Path:
    for name, usd in V7_COSTS.items():
        write_cost_run(root, name, usd)
    return root


def write_questions(root: Path, corpus: str, n: int) -> None:
    (root / corpus).mkdir(parents=True)
    (root / corpus / "questions.jsonl").write_text('{"q": 1}\n' * n)


def write_prompt_sizes(path: Path, tokens: dict[str, int] | None = None) -> Path:
    rows = [{"corpus_id": c, "est_prompt_tokens": t} for c, t in (tokens or PROMPT_TOKENS).items()]
    path.write_text(json.dumps(rows))
    return path


def write_e1_ctx_runs(root: Path) -> Path:
    for size, completion in E1_COMPLETION.items():
        run = root / f"E1-CTXH-{size}"
        run.mkdir(parents=True)
        rows = [{"completion_tokens": completion - 10}, {"completion_tokens": completion + 10}]
        (run / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return root
