"""Caps of the ContextRAG reference arm on the small ladder (H1g2, H3g2, H10g2), high effort.

ContextRAG pastes the whole plant into one prompt, so its cost is the prompt size times the
billed input price, plus the answer. The prompt size is the free `prompt-size` measurement of
the real ladder corpora (`make_set.sh` writes it before the caps); the answer length is the mean
completion of EXP-0001's ContextRAG-high run at the matching v1 size, doubled because the plan's
range for v2 answers is 1x to 2x (plan section 8). Cap: `ceil_0.05(1.3 x n x c)`.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0001.prompt_size import PRICE_STEP_TOKENS
from plantgraph.qa.exp0007.cap_plans import count_questions
from plantgraph.qa.exp0007.caps import CapEntry, cap_usd

#: The v2 ladder sizes it runs on -> the EXP-0001 size whose ContextRAG-high run sets the answer.
CTX_SIZES = {"H1g2": "H1", "H3g2": "H3", "H10g2": "H10"}
#: Billed prices below the 272k-token step, dollars per million tokens (plan section 8: least
#: squares over 513 ContextRAG rows; the prompt price equals the listing's `input_cache_write`).
PROMPT_USD_PER_M = 0.125
COMPLETION_USD_PER_M = 0.5
COMPLETION_FACTOR = 2.0
SMOKE_QUESTIONS = 2


class _PromptRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    corpus_id: str
    est_prompt_tokens: int


class _AnswerRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    completion_tokens: int | None = None


def read_prompt_tokens(prompt_size_json: Path) -> dict[str, int]:
    """Corpus id -> prompt tokens, from the file `exp0001 prompt-size --json` wrote."""
    rows = json.loads(prompt_size_json.read_text(encoding="utf-8"))
    return {r.corpus_id: r.est_prompt_tokens for r in map(_PromptRow.model_validate, rows)}


def mean_completion_tokens(run_dir: Path) -> float:
    """Mean completion tokens per question of a stored ContextRAG run.

    Raises:
        FileNotFoundError: the run has no `answers.jsonl`.
        ValueError: the run has no row with a completion count.
    """
    path = run_dir / "answers.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"expected {path}, found none")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    counts = [
        row.completion_tokens
        for row in (_AnswerRow.model_validate_json(line) for line in lines)
        if row.completion_tokens is not None
    ]
    if not counts:
        raise ValueError(f"expected completion token counts in {path}, found none")
    return sum(counts) / len(counts)


def cost_per_question(prompt_tokens: int, completion_tokens: float) -> float:
    """Dollars for one ContextRAG question at the billed prices below the price step.

    Raises:
        ValueError: the prompt is above the price step (its billed price is unmeasured).
    """
    if prompt_tokens > PRICE_STEP_TOKENS:
        raise ValueError(
            f"expected a prompt of at most {PRICE_STEP_TOKENS} tokens (below the price step), "
            f"found {prompt_tokens}"
        )
    answer = completion_tokens * COMPLETION_FACTOR * COMPLETION_USD_PER_M
    return (prompt_tokens * PROMPT_USD_PER_M + answer) / 1_000_000


def _entry(run_id: str, n: int, cost: float, basis: str) -> CapEntry:
    return CapEntry(
        run_id=run_id,
        tier="ctx",
        n_questions=n,
        v1_cost_per_question_usd=cost,
        correction=1.0,
        cost_per_question_usd=cost,
        cap_usd=cap_usd(n, cost),
        basis=basis,
    )


def ctx_small_entries(
    prompt_size_json: Path, e1_runs: Path, ladder_questions: Path
) -> list[CapEntry]:
    """A 2-question smoke on H1g2, then a full run per small size, all `E7-CTXH-*`."""
    tokens = read_prompt_tokens(prompt_size_json)
    entries: list[CapEntry] = []
    for corpus, v1_corpus in CTX_SIZES.items():
        if corpus not in tokens:
            raise ValueError(f"expected a prompt size for {corpus}, found {sorted(tokens)}")
        completion = mean_completion_tokens(e1_runs / f"E1-CTXH-{v1_corpus}")
        cost = cost_per_question(tokens[corpus], completion)
        basis = (
            f"{tokens[corpus]} prompt tokens x ${PROMPT_USD_PER_M}/M + {COMPLETION_FACTOR:g} x "
            f"{completion:.0f} completion tokens (E1-CTXH-{v1_corpus}) x ${COMPLETION_USD_PER_M}/M"
        )
        n = count_questions(ladder_questions / corpus / "questions.jsonl")
        if corpus == "H1g2":
            entries.append(_entry("E7-CTXH-H1g2-SMOKE", SMOKE_QUESTIONS, cost, basis))
        entries.append(_entry(f"E7-CTXH-{corpus}", n, cost, basis))
    return entries
