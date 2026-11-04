"""The commands that call the D4 model: `decide --decider d4`, `pilot` and `open100`.

Each opens its own cache-only or paid session (`d4_session`), so without `--allow-paid-calls` it
stops at the first uncached card, with no network request.
"""

from __future__ import annotations

import random
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.exp0004 import storage
from plantgraph.exp0004.commands import rebuild
from plantgraph.exp0004.d4_decider import ChatPairDecider
from plantgraph.exp0004.d4_open100 import OPEN100_TAG_PAIRS, Open100Answer, text_only_card
from plantgraph.exp0004.d4_prompt import prompt_sha256
from plantgraph.exp0004.d4_session import LlmOptions, open_decider
from plantgraph.exp0004.d4_stats import LlmStats, PairCall, summarize
from plantgraph.exp0004.deciders import DeciderRun, run_decider

PILOT_SEED = 0
PARSE_FAILURE_LIMIT = 0.02  # design 5.4: above this the prompt is fixed on dev first


class PilotSummary(BaseModel):
    """What `pilot` writes as `pilot/summary.json`."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    seed: int
    pair_indices: list[int]
    stats: LlmStats
    parse_failures_over_limit: bool


class PairCalls(BaseModel):
    """The per-call records, written next to a decision or a pilot summary."""

    calls: list[PairCall]


def decide_d4(directory: Path, options: LlmOptions) -> DeciderRun:
    """Run D4 on every candidate pair of the corpus in `directory`."""
    corpus = rebuild(directory)
    log_path = directory / "decisions" / "d4_llm_calls.jsonl"
    run_id = f"exp0004-d4-{corpus.spec.corpus_id}"
    with open_decider(options, log_path, run_id) as (decider, pin):
        run = run_decider(corpus, decider)
        stats = summarize(decider.calls, pin.pin_hash(), prompt_sha256())
    run = run.model_copy(update={"llm": stats})
    storage.write_model(storage.decision_path(directory, "d4"), run)
    storage.write_model(directory / "decisions" / "d4_calls.json", PairCalls(calls=decider.calls))
    return run


def sample_indices(n_pairs: int, n_sample: int, seed: int = PILOT_SEED) -> list[int]:
    """`n_sample` distinct pair positions, the same for the same inputs, in ascending order."""
    if not 0 < n_sample <= n_pairs:
        raise ValueError(f"expected 1 to {n_pairs} pairs to sample, got {n_sample}")
    return sorted(random.Random(seed).sample(range(n_pairs), n_sample))


def pilot(directory: Path, n_pairs: int, options: LlmOptions) -> PilotSummary:
    """Ask D4 about a deterministic sample of a dev corpus and report the parse-failure rate."""
    corpus = rebuild(directory)
    pairs = corpus.candidates.pairs
    indices = sample_indices(len(pairs), n_pairs)
    out = directory / "pilot"
    with open_decider(options, out / "llm_calls.jsonl", "exp0004-d4-pilot") as (decider, pin):
        for index in indices:
            decider.decide(pairs[index])
        stats = summarize(decider.calls, pin.pin_hash(), prompt_sha256())
    summary = PilotSummary(
        corpus_id=corpus.spec.corpus_id,
        seed=PILOT_SEED,
        pair_indices=indices,
        stats=stats,
        parse_failures_over_limit=(stats.parse_failure_rate or 0.0) > PARSE_FAILURE_LIMIT,
    )
    storage.write_model(out / "calls.json", PairCalls(calls=decider.calls))
    storage.write_model(out / "summary.json", summary)
    return summary


def open100(out: Path, options: LlmOptions) -> list[Open100Answer]:
    """Run the OPEN100 text-only cards through D4 and write the answers to `out`."""
    with open_decider(options, out.with_suffix(".jsonl"), "exp0004-d4-open100") as (decider, _):
        answers = [_open100_answer(decider, first, second) for first, second in OPEN100_TAG_PAIRS]
    storage.write_text(out, _answers_json(answers))
    return answers


def _open100_answer(decider: ChatPairDecider, first_tag: str, second_tag: str) -> Open100Answer:
    call = decider.ask(text_only_card(first_tag, second_tag))
    return Open100Answer(
        first_tag=first_tag,
        second_tag=second_tag,
        card=call.card,
        answer_text=call.answer_text,
        same_item=call.same_item,
        reason=call.reason,
    )


def _answers_json(answers: list[Open100Answer]) -> str:
    return "[" + ",\n".join(answer.model_dump_json() for answer in answers) + "]\n"
