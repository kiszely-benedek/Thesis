"""Read the stored harness runs of one corpus and score every arm, reusing the cascade's join.

Answer to design question O2: `cascade report` takes a one-tier `context_rag` policy and lists a
policy whose first run is missing as "not evaluated", but its report keeps only summaries, not
per-question scores. The paired tests here need per-question scores, so this module calls the same
`join_corpus` + `evaluate_policy` that `cascade report` calls, and keeps the per-question result.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.corpus_checks import load_corpus_view
from plantgraph.qa.cascade.evaluate import ScoredDecision, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.labels import anchor_finder
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.exp0001.report_models import CTX_HIGH, CTX_LOW, QuestionScore, SizePoint

#: Strategy of a tier -> the run arm whose directory holds its rows (ContextRAG: the arm itself).
RUN_ARM_OF_STRATEGY = {
    "cypher_rag_plant": "cyp",
    "graph_agent_low_steps": "ag",
    "cypher_rag_lines": "cyp",  # V2T (ADR-0061)
    "graph_agent_lines": "ag",
}
CONTEXT_STRATEGY = "context_rag"


@dataclass(frozen=True)
class CorpusInputs:
    """Where one corpus's questions, ingest result and stored runs are."""

    corpus_id: str
    #: Holds `<corpus>/questions.jsonl`: the question set every arm is scored on.
    questions_root: Path
    #: Holds `<corpus>/ingest.json`, for the size of the corpus.
    corpora_root: Path
    #: Run arm (ctx-high, ctx-low, cyp, ag) -> its harness run directory; only runs that exist.
    run_dirs: Mapping[str, Path]
    #: Questions root the cyp/ag runs were started from, when not `questions_root` (H100 reuses
    #: the sealed runs, which cover a larger question file than the 24-question subsample).
    tier_questions_root: Path | None = None


@dataclass
class CtxCall:
    """One ContextRAG-high call: characters sent and tokens the provider counted."""

    chars: int
    tokens: int


@dataclass
class CorpusScores:
    """The per-question scores of every arm that could be scored on one corpus."""

    size: SizePoint
    #: Arm -> scores in question-file order.
    scores: dict[str, list[QuestionScore]] = field(default_factory=dict)
    #: Families of the corpus's questions (the question file's, before scope filtering).
    families: frozenset[str] = frozenset()
    ctx_calls: list[CtxCall] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)


class _Counts(BaseModel):
    n_sheets: int
    n_nodes: int


class _Layers(BaseModel):
    n_occurrences: int


class _IngestSizes(BaseModel):
    """The few fields of an `ingest.json` the report needs (other fields are ignored)."""

    counts: _Counts
    layer_counts: _Layers | None = None


def read_sizes(corpora_root: Path, corpus_id: str) -> tuple[int, int]:
    """(sheets, occurrence nodes) of a corpus; nodes fall back to the store count without layers."""
    path = corpora_root / corpus_id / "ingest.json"
    if not path.exists():
        raise FileNotFoundError(f"expected an ingest result at {path}, found none")
    result = _IngestSizes.model_validate_json(path.read_text(encoding="utf-8"))
    layers = result.layer_counts
    return result.counts.n_sheets, layers.n_occurrences if layers else result.counts.n_nodes


def score_corpus(
    inputs: CorpusInputs, policies: Mapping[str, CascadePolicy], cutoff_s: float
) -> CorpusScores:
    """Join and score every arm whose runs exist; list the others as absent with the reason."""
    _, questions = load_questions_file(inputs.questions_root, inputs.corpus_id)
    family_of = {q.question_id: q.family.value for q in questions}
    n_sheets, n_nodes = read_sizes(inputs.corpora_root, inputs.corpus_id)
    result = CorpusScores(
        size=SizePoint(
            corpus_id=inputs.corpus_id,
            n_sheets=n_sheets,
            n_occurrence_nodes=n_nodes,
            ctx_prompt_chars=None,
            ctx_prompt_tokens_median=None,
            chars_per_token=None,
        ),
        families=frozenset(family_of.values()),
    )
    graph_hashes: dict[str, str] = {}
    for arm, policy in policies.items():
        sources = _tier_sources(arm, policy, inputs)
        if isinstance(sources, str):
            result.absent.append(f"{arm} at {inputs.corpus_id}: {sources}")
            continue
        joined = _join(arm, policy, sources, inputs)
        graph_hashes[arm] = joined.reference.record.source_graph_hash
        result.scores[arm] = _score_arm(joined, family_of, cutoff_s)
        if arm == CTX_HIGH:
            result.ctx_calls = _ctx_calls(joined)
    _require_same_plant(inputs.corpus_id, graph_hashes)
    _fill_ctx_size(result)
    return result


def _tier_sources(
    arm: str, policy: CascadePolicy, inputs: CorpusInputs
) -> dict[str, TierSource] | str:
    """Tier name -> its run, or the reason (a string) when some tier of the policy has no run."""
    sources: dict[str, TierSource] = {}
    for tier in policy.tiers:
        is_context = tier.strategy == CONTEXT_STRATEGY
        run_arm = arm if is_context else RUN_ARM_OF_STRATEGY.get(tier.strategy, "")
        run_dir = inputs.run_dirs.get(run_arm)
        if run_dir is None:
            return f"no run for tier {tier.name!r} (arm {run_arm!r})"
        sources[tier.name] = TierSource(run_dir, None if is_context else inputs.tier_questions_root)
    return sources


def _join(
    arm: str, policy: CascadePolicy, sources: dict[str, TierSource], inputs: CorpusInputs
) -> JoinedCorpus:
    """Join with the questions root the policy's first tier was started from; require every row."""
    is_context_arm = arm in (CTX_HIGH, CTX_LOW)
    root = inputs.tier_questions_root or inputs.questions_root
    # a policy routed by need label (cascade_v4_iso) reads each question's label from its text
    routed = bool(policy.start_tier_by_label or policy.last_tier_by_label)
    finder = (
        anchor_finder(load_corpus_view(inputs.corpora_root, inputs.corpus_id)) if routed else None
    )
    joined = join_corpus(
        policy,
        sources,
        inputs.corpus_id,
        inputs.questions_root if is_context_arm else root,
        find_anchors=finder,
    )
    require_complete(joined)
    return joined


def _score_arm(
    joined: JoinedCorpus, family_of: Mapping[str, str], cutoff_s: float
) -> list[QuestionScore]:
    """The policy's scored decisions, restricted to and ordered by the report's question set."""
    scored = {s.decision.question_id: s for s in evaluate_policy(joined, cutoff_s).scored}
    missing = [qid for qid in family_of if qid not in scored]
    if missing:
        raise ValueError(
            f"expected {joined.policy.name!r} to answer all {len(family_of)} report questions, "
            f"found {len(missing)} missing, e.g. {missing[:3]}"
        )
    return [_question_score(joined, scored[qid], family) for qid, family in family_of.items()]


def _question_score(joined: JoinedCorpus, scored: ScoredDecision, family: str) -> QuestionScore:
    decision = scored.decision
    final_tier = decision.answered_by or decision.tiers_tried[-1]
    row = joined.runs[final_tier].rows[decision.question_id]
    return QuestionScore(
        qid=decision.question_id,
        family=family,
        correct=scored.correct,
        correct_at_cutoff=scored.correct_at_cutoff,
        cost_usd=decision.cost_usd,
        latency_s=decision.latency_s,
        outcome=row.outcome,
    )


def _ctx_calls(joined: JoinedCorpus) -> list[CtxCall]:
    """Prompt size of every ContextRAG call that reached the provider (tokens counted)."""
    rows = joined.runs[joined.policy.tiers[0].name].rows.values()
    return [CtxCall(r.context_chars, r.prompt_tokens) for r in rows if r.prompt_tokens > 0]


def _require_same_plant(corpus_id: str, graph_hashes: Mapping[str, str]) -> None:
    if len(set(graph_hashes.values())) > 1:
        raise ValueError(
            f"expected every arm on {corpus_id} to read the same plant (source_graph_hash), "
            f"found {dict(graph_hashes)}"
        )


def _fill_ctx_size(result: CorpusScores) -> None:
    """Put ContextRAG's median prompt chars/tokens and chars-per-token into the size point."""
    calls = result.ctx_calls
    if not calls:
        return
    result.size = result.size.model_copy(
        update={
            "ctx_prompt_chars": int(statistics.median(c.chars for c in calls)),
            "ctx_prompt_tokens_median": int(statistics.median(c.tokens for c in calls)),
            "chars_per_token": statistics.median(c.chars / c.tokens for c in calls),
        }
    )
