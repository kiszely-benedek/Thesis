"""Build the V2T tuning report: cascade_v4 and cascade_v4_iso under one limit setting.

Joins the two stored tier runs (Cypher and agent) for each policy, scores them against gold
and adds what the tuning protocol reads: uncut accuracy (primary), accuracy within 120 s and
300 s (secondary), the oracle gap, the Cypher accept rule's rejections and the pre-registered
choice between the two variants. It refuses runs that do not match the setting.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from plantgraph.qa.cascade.accept import first_failed_rule
from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.corpus_checks import load_corpus_view
from plantgraph.qa.cascade.evaluate import Evaluation, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.labels import anchor_finder
from plantgraph.qa.cascade.limits import LimitSetting, run_problems
from plantgraph.qa.cascade.models import AcceptRule
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policies
from plantgraph.qa.cascade.report_groups import DIM_FAMILY, breakdown, question_groups
from plantgraph.qa.cascade.report_models import Cell
from plantgraph.qa.cascade.tune_models import (
    SECONDARY_CUTOFFS_S,
    CypherAcceptance,
    TuneReport,
    VariantResult,
)
from plantgraph.qa.cascade.tune_select import (
    TUNING_CORPUS_ID,
    V4,
    V4_ISO,
    VariantChoice,
    select_variant,
)

#: Family -> policy -> correct/total, as `report_groups.breakdown` returns it.
FamilyCells = dict[str, dict[str, Cell]]


def correct_within(evaluation: Evaluation, cutoff_s: float) -> int:
    """Correct answers that arrived within `cutoff_s` seconds."""
    return sum(s.correct and s.decision.latency_s <= cutoff_s for s in evaluation.scored)


def two_tier_oracle(joined: JoinedCorpus) -> int:
    """Questions that at least one tier answered correctly (needs both tiers' rows for all)."""
    first, second = (joined.runs[tier.name].rows for tier in joined.policy.tiers)
    missing = [q for q in joined.question_ids if q not in first or q not in second]
    if missing:
        raise ValueError(f"expected a row in both tiers for every question, missing {missing[:3]}")
    return sum(first[q].correct or second[q].correct for q in joined.question_ids)


def cypher_acceptance(joined: JoinedCorpus) -> CypherAcceptance:
    """How the first tier's accept rule judged each answer, and how many correct ones it dropped."""
    tier = joined.policy.tiers[0]
    rows = joined.runs[tier.name].rows
    rejected: Counter[str] = Counter()
    accepted = accepted_correct = cut_but_correct = 0
    for qid in joined.question_ids:
        failed = first_failed_rule(joined.signals[tier.name][qid], tier.accept)
        if failed is None:
            accepted += 1
            accepted_correct += rows[qid].correct
            continue
        rejected[failed.value] += 1
        cut_but_correct += failed is AcceptRule.COMPLETE and rows[qid].correct
    return CypherAcceptance(
        n_tried=len(joined.question_ids),
        n_accepted=accepted,
        n_accepted_correct=accepted_correct,
        rejected_by=dict(rejected),
        n_cut_but_correct=cut_but_correct,
    )


def variant_result(evaluation: Evaluation, by_family: FamilyCells) -> VariantResult:
    """The numbers of one evaluated policy; `by_family` covers every evaluated policy."""
    summary = evaluation.summary
    return VariantResult(
        policy=summary.policy,
        n_questions=summary.n_questions,
        n_correct_uncut=summary.n_correct,
        n_correct_in_limit=summary.n_correct_at_cutoff,
        n_beyond_limit=summary.n_timed_out,
        n_correct_within={f"{c:g}": correct_within(evaluation, c) for c in SECONDARY_CUTOFFS_S},
        latency_median_s=summary.latency_median_s,
        latency_p90_s=summary.latency_p90_s,
        cost_per_question_usd=summary.cost_per_question_usd,
        tier_shares=summary.tier_shares,
        by_family={family: cells[summary.policy] for family, cells in by_family.items()},
        correct_ids=tuple(s.decision.question_id for s in evaluation.scored if s.correct),
    )


def build_tune_report(
    corpus_id: str,
    setting: LimitSetting,
    sources: Mapping[str, TierSource],
    questions_root: Path,
    corpora_root: Path,
) -> TuneReport:
    """Evaluate cascade_v4 and cascade_v4_iso on one corpus under `setting`.

    `corpora_root` holds `<corpus>/ingest.json`: the iso policy routes by need label, and the
    label comes from the question text and the corpus's tags.

    Raises:
        ValueError: a run does not match the setting, or a tier has no row for a question.
    """
    policies = load_policies(V2T_POLICIES_DIR)
    _, questions = load_questions_file(questions_root, corpus_id)
    finder = anchor_finder(load_corpus_view(corpora_root, corpus_id))
    joins = {
        name: join_corpus(policies[name], dict(sources), corpus_id, questions_root, finder)
        for name in (V4, V4_ISO)
    }
    problems = run_problems(setting, joins[V4].runs)
    if problems:
        raise ValueError("expected runs that match the setting, found:\n  " + "\n  ".join(problems))
    evaluations: dict[str, Evaluation] = {}
    for name, joined in joins.items():
        require_complete(joined)
        evaluations[name] = evaluate_policy(joined, setting.cutoff_s)
    family_of = question_groups(questions, {})[DIM_FAMILY]
    by_family = breakdown(evaluations, family_of, DIM_FAMILY)
    results = {name: variant_result(ev, by_family) for name, ev in evaluations.items()}
    return TuneReport(
        corpus_id=corpus_id,
        setting=setting,
        n_questions=len(questions),
        oracle_correct=two_tier_oracle(joins[V4]),
        results=results,
        cypher=cypher_acceptance(joins[V4]),
        choice=_choice(corpus_id, setting, results),
    )


def primary_correct(result: VariantResult, setting: LimitSetting) -> int:
    """The count a setting is judged on: A within its 120 s limit, B uncut (no deadline)."""
    return result.n_correct_in_limit if setting.name == "A" else result.n_correct_uncut


def _choice(
    corpus_id: str, setting: LimitSetting, results: Mapping[str, VariantResult]
) -> VariantChoice | None:
    """The pre-registered choice on the setting's primary number; only defined on T."""
    if corpus_id != TUNING_CORPUS_ID:
        return None
    v4, iso = results[V4], results[V4_ISO]
    return select_variant(
        corpus_id,
        setting.name,
        v4.n_questions,
        primary_correct(v4, setting),
        primary_correct(iso, setting),
    )
