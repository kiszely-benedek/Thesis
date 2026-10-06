"""Build the cascade report: every policy on every corpus, its references, and S1-S3.

Per corpus each policy is joined, checked for gaps and scored against gold. A policy whose
join is refused or incomplete is listed with the reason instead of being evaluated: a table
never contains a number that rests on rows that do not exist.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.evaluate import (
    Evaluation,
    Summary,
    compare,
    evaluate_policy,
    first_tier_acceptance,
)
from plantgraph.qa.cascade.gaps import IncompleteJoinError
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policies
from plantgraph.qa.cascade.references import evaluate_oracle, random_escalation
from plantgraph.qa.cascade.report_groups import breakdown, question_groups
from plantgraph.qa.cascade.report_models import (
    AcceptanceResult,
    CorpusReport,
    NotEvaluated,
    PolicyResult,
    RandomSummary,
    Report,
    Tier3Tally,
    Verdict,
)
from plantgraph.qa.cascade.report_verdicts import (
    CONFIRM_CORPUS,
    LABEL_VARIANTS,
    PRIMARY,
    RUNAWAY_TIER,
    TIER3_CANDIDATES,
    check_label_variant,
    confirm_cascade,
    select_tier3,
    tally_tier3,
)
from plantgraph.qa.models import Question

ALWAYS_N = "always_n"
#: The always-one-tier baselines are part of every report, whatever `--policy` selects.
BASELINES = (ALWAYS_N, "always_c")

#: corpus id -> tier name -> where that tier's stored run lives.
SourcesByCorpus = Mapping[str, Mapping[str, TierSource]]


def _has_references(policy: CascadePolicy) -> bool:
    """Oracle and random escalation are defined for label-free policies with 2+ tiers."""
    routed = policy.start_tier_by_label or policy.last_tier_by_label
    return len(policy.tiers) >= 2 and not routed


def _acceptance(joined: JoinedCorpus) -> AcceptanceResult | None:
    policy = joined.policy
    if len(policy.tiers) < 2 or policy.start_tier_by_label:
        return None  # a single tier accepts everything; a router skips tier 1 for some labels
    raw = first_tier_acceptance(joined, policy)
    return AcceptanceResult(
        n_accepted=raw.n_accepted,
        n_accepted_correct=raw.n_accepted_correct,
        n_first_tier_correct=raw.n_first_tier_correct,
        precision=raw.precision,
        recall=raw.recall,
    )


def _reference_fields(joined: JoinedCorpus, evaluation: Evaluation) -> dict[str, object]:
    """Oracle and random escalation, or the reason they cannot be computed on these rows."""
    if not _has_references(joined.policy):
        return {}
    try:
        reference = random_escalation(joined)
        oracle = evaluate_oracle(joined)
    except ValueError as error:  # e.g. the second tier has rows only for the runaways
        return {"references_skipped": str(error)}
    return {
        "oracle": oracle.summary,
        "random": RandomSummary(
            n_draws=reference.n_draws,
            n_escalated=reference.n_escalated,
            correct_mean=reference.correct_mean,
            correct_low=reference.correct_low,
            correct_high=reference.correct_high,
            cost_total_mean_usd=reference.cost_total_mean_usd,
            latency_mean_s=reference.latency_mean_s,
        ),
        "vs_random": compare(evaluation.series(), reference.series()),
    }


def _policy_result(
    joined: JoinedCorpus, evaluation: Evaluation, always_n: Evaluation | None
) -> PolicyResult:
    """One policy's row: summary, acceptance, and (where defined) references and comparisons."""
    fields = _reference_fields(joined, evaluation)
    if always_n is not None and joined.policy.name != ALWAYS_N:
        fields["vs_always_n"] = compare(evaluation.series(), always_n.series())
    fields |= {"summary": evaluation.summary, "acceptance": _acceptance(joined)}
    return PolicyResult.model_validate(fields)


def _evaluate_all(
    corpus_id: str,
    policies: Sequence[CascadePolicy],
    sources: Mapping[str, TierSource],
    questions_root: Path,
) -> tuple[dict[str, JoinedCorpus], dict[str, Evaluation], list[NotEvaluated]]:
    """Join every policy; evaluate those that are complete, list the others with the reason."""
    joins: dict[str, JoinedCorpus] = {}
    evaluations: dict[str, Evaluation] = {}
    problems: list[NotEvaluated] = []
    for policy in policies:
        try:
            joined = join_corpus(policy, dict(sources), corpus_id, questions_root)
            joins[policy.name] = joined
            require_complete(joined)
            evaluations[policy.name] = evaluate_policy(joined)
        except IncompleteJoinError as error:
            gaps = {tier: len(ids) for tier, ids in error.gaps.items()}
            problems.append(NotEvaluated(policy=policy.name, reason=str(error), gaps=gaps))
        except ValueError as error:  # refused join, or a need label the policy needs is missing
            problems.append(NotEvaluated(policy=policy.name, reason=str(error)))
    return joins, evaluations, problems


def _corpus_report(
    corpus_id: str,
    questions: list[Question],
    joins: Mapping[str, JoinedCorpus],
    evaluations: Mapping[str, Evaluation],
    problems: list[NotEvaluated],
) -> CorpusReport:
    always_n = evaluations.get(ALWAYS_N)
    results = [_policy_result(joins[name], ev, always_n) for name, ev in evaluations.items()]
    # Each join takes need labels from its own runs' traces; the union covers every question.
    labels = {qid: lab for joined in joins.values() for qid, lab in joined.need_labels.items()}
    by_dimension = question_groups(questions, labels)
    return CorpusReport(
        corpus_id=corpus_id,
        n_questions=len(questions),
        policies=results,
        not_evaluated=problems,
        breakdowns={
            dimension: breakdown(evaluations, group_of, dimension)
            for dimension, group_of in by_dimension.items()
        },
    )


def _join_with(candidate: str, joins: Sequence[JoinedCorpus]) -> JoinedCorpus:
    """A join holding the candidate's run if one does, else any join with the runaway tier."""
    return next((j for j in joins if candidate in j.runs), joins[0])


def _tier3_verdict(
    joins_by_corpus: Mapping[str, Mapping[str, JoinedCorpus]],
) -> tuple[Verdict, list[Tier3Tally]]:
    """S1 over the corpora given; INCOMPLETE if one has no join holding the runaway tier."""
    usable = {
        corpus: [j for j in joins.values() if RUNAWAY_TIER in j.runs]
        for corpus, joins in joins_by_corpus.items()
    }
    missing = [corpus for corpus, joins in usable.items() if not joins]
    if missing:
        headline = f"no {RUNAWAY_TIER} run joined for {', '.join(missing)}"
        return Verdict(rule="S1", status="INCOMPLETE", headline=headline), []
    tallies = [
        tally_tier3([_join_with(candidate, joins) for joins in usable.values()], candidate)
        for candidate in TIER3_CANDIDATES
    ]
    verdict = select_tier3(tallies)
    details = [*verdict.details, f"dev corpora pooled: {', '.join(usable)}"]
    return verdict.model_copy(update={"details": details}), tallies


def _confirmation_verdicts(corpora: Sequence[CorpusReport]) -> list[Verdict]:
    """S2 and S3, both judged on `CONFIRM_CORPUS`."""
    confirm = next((c for c in corpora if c.corpus_id == CONFIRM_CORPUS), None)
    summaries: dict[str, Summary] = {}
    if confirm is not None:
        summaries = {r.summary.policy: r.summary for r in confirm.policies}
    verdicts = [confirm_cascade(summaries.get(PRIMARY), summaries.get(ALWAYS_N))]
    for variant in LABEL_VARIANTS:
        verdicts.append(
            check_label_variant(variant, summaries.get(variant), summaries.get(PRIMARY))
        )
    return verdicts


def _with_baselines(policies: Sequence[CascadePolicy] | None) -> list[CascadePolicy]:
    available = load_policies(POLICIES_DIR)
    chosen = {p.name: p for p in (available.values() if policies is None else policies)}
    for name in BASELINES:
        chosen.setdefault(name, available[name])
    return list(chosen.values())


def build_report(
    corpus_ids: Sequence[str],
    sources: SourcesByCorpus,
    questions_root: Path,
    policies: Sequence[CascadePolicy] | None = None,
) -> Report:
    """Evaluate `policies` (default: every policy file, plus the baselines) on each corpus."""
    chosen = _with_baselines(policies)
    reports: list[CorpusReport] = []
    all_joins: dict[str, dict[str, JoinedCorpus]] = {}
    for corpus_id in corpus_ids:
        _, questions = load_questions_file(questions_root, corpus_id)
        joins, evaluations, problems = _evaluate_all(
            corpus_id, chosen, sources.get(corpus_id, {}), questions_root
        )
        all_joins[corpus_id] = joins
        reports.append(_corpus_report(corpus_id, questions, joins, evaluations, problems))
    s1, tallies = _tier3_verdict(all_joins)
    return Report(corpora=reports, tier3=tallies, verdicts=[s1, *_confirmation_verdicts(reports)])
