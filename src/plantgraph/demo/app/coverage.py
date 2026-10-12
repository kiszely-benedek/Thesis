"""`coverage`: ask every benchmark question of a corpus from the cache alone and count what answers.

The demo promises that its example questions are free and give the answer the experiment
recorded. This command checks the promise: a *hit* is a question whose every model call is in
the cache, a *miss* is one that would need a paid call. A cache is a stored copy of earlier
model replies, so a replay costs nothing.

Replay-only is structural, not a flag: the loader is built with paid calls off (so a paid
cascade cannot even be opened) and this module only ever asks for the replay cascade.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from plantgraph.demo.app.api_models import RecordedAnswer
from plantgraph.demo.app.cascade_pool import CascadeSource
from plantgraph.demo.app.config import DemoConfig, load_demo_config
from plantgraph.demo.app.state import build_app_state
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall
from plantgraph.qa.models import Question

#: Key in `answered_by` for a hit that no tier answered (failed or too late).
NO_TIER = "(no tier answer)"


class CorpusCoverage(BaseModel):
    """What replaying one corpus's questions found."""

    corpus_id: str
    #: The policy that ran; a derived name (`...-no-cypher-luna`) when a tier was unavailable.
    policy: str
    tiers: tuple[str, ...]
    n_questions: int
    n_hits: int
    #: Tier that would need a paid call -> number of questions.
    misses_by_tier: dict[str, int]
    #: Answering tier -> number of hits it answered.
    answered_by: dict[str, int]
    #: Hits whose answering tier has a recorded row for the question.
    n_comparable: int
    #: Comparable hits whose final answer equals a recorded row's answer of the same strategy.
    n_equal: int


def measure_coverage(
    corpus_id: str,
    questions: Mapping[str, Question],
    recorded: Mapping[str, tuple[RecordedAnswer, ...]],
    source: CascadeSource,
) -> CorpusCoverage:
    """Replay every question through `source`'s replay cascade and count the outcomes."""
    asker = source.asker(paid=False, tier2_only=False)  # the only cascade this module opens
    misses: Counter[str] = Counter()
    answered_by: Counter[str] = Counter()
    n_hits = n_comparable = n_equal = 0
    policy = ""
    for question in questions.values():
        result = asker.ask(question)
        if isinstance(result, NeedsPaidCall):
            misses[result.missing_tier] += 1
            continue
        n_hits += 1
        policy = result.policy
        answered_by[result.answered_by or NO_TIER] += 1
        verdict = _compare_with_recorded(result, recorded.get(question.question_id, ()))
        n_comparable += verdict is not None
        n_equal += verdict is True
    return CorpusCoverage(
        corpus_id=corpus_id,
        policy=policy,
        tiers=source.tiers,
        n_questions=len(questions),
        n_hits=n_hits,
        misses_by_tier=dict(misses),
        answered_by=dict(answered_by),
        n_comparable=n_comparable,
        n_equal=n_equal,
    )


def _compare_with_recorded(live: LiveAnswer, rows: tuple[RecordedAnswer, ...]) -> bool | None:
    """Is the live answer equal to a recorded one of that strategy? `None`: no row to compare."""
    winner = next((t for t in live.tiers if t.tier == live.answered_by), None)
    if winner is None or live.final_answer is None:
        return None
    same_strategy = [row for row in rows if row.strategy == winner.strategy]
    if not same_strategy:
        return None
    return any(row.answer == live.final_answer.answer for row in same_strategy)


def format_coverage(coverage: CorpusCoverage) -> str:
    """The report for one corpus as plain text."""
    return "\n".join(
        [
            f"corpus {coverage.corpus_id}  policy {coverage.policy or '(none ran)'}"
            f"  tiers {list(coverage.tiers)}",
            f"  questions asked : {coverage.n_questions}",
            f"  full cache hits : {coverage.n_hits}/{coverage.n_questions}",
            f"  misses per tier : {coverage.misses_by_tier or 'none'}",
            f"  answered by     : {coverage.answered_by or 'nobody'}",
            f"  answers equal to the recorded runs: {coverage.n_equal}/{coverage.n_comparable}"
            f" comparable of {coverage.n_hits} hits",
        ]
    )


def build_coverage_parser(prog: str = "coverage") -> argparse.ArgumentParser:
    """The `coverage` command line: the demo config and optionally which corpora."""
    parser = argparse.ArgumentParser(
        prog=prog, description="Replay every benchmark question from the cache; never pays."
    )
    parser.add_argument("--config", type=Path, required=True, help="the demo config JSON")
    parser.add_argument(
        "--corpus", action="append", help="corpus id to check; repeat it. Default: all configured"
    )
    return parser


def run_coverage(argv: Sequence[str]) -> None:
    """Entry point for `python -m plantgraph.demo.app coverage ...`; prints one block per corpus."""
    args = build_coverage_parser().parse_args(argv)
    config = _select_corpora(load_demo_config(args.config), args.corpus)
    # paid calls off: the pool refuses to open a paid cascade, whatever this module asks for
    state = build_app_state(config, allow_paid_calls=False)
    try:
        state.load_all()  # a failed load is recorded on its slot; ready_corpus then raises it
        for corpus in config.corpora:
            loaded = state.ready_corpus(corpus.corpus_id)
            coverage = measure_coverage(
                corpus.corpus_id, loaded.questions, loaded.recorded, loaded.source
            )
            print(format_coverage(coverage))
    finally:
        state.close()


def _select_corpora(config: DemoConfig, wanted: Sequence[str] | None) -> DemoConfig:
    if not wanted:
        return config
    unknown = [corpus_id for corpus_id in wanted if config.corpus(corpus_id) is None]
    if unknown:
        known = [c.corpus_id for c in config.corpora]
        raise ValueError(f"expected corpus ids among {known}, found {unknown}")
    kept = tuple(c for c in config.corpora if c.corpus_id in wanted)
    return config.model_copy(update={"corpora": kept})
