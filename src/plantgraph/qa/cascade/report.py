"""Build the cascade report: every policy on every corpus, its references, S1-S3 and V2-V3.

Per corpus each policy is joined, checked for gaps and scored against gold. A policy whose
join is refused or incomplete is listed with the reason instead of being evaluated: a table
never contains a number that rests on rows that do not exist.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.corpus_checks import load_corpus_view, load_sheet_count
from plantgraph.qa.cascade.diagnostics import policy_diagnostics
from plantgraph.qa.cascade.evaluate import (
    Evaluation,
    LatencyBound,
    Summary,
    compare,
    evaluate_policy,
)
from plantgraph.qa.cascade.gaps import IncompleteJoinError
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.labels import AnchorFinder, anchor_finder, labels_from_run_dirs
from plantgraph.qa.cascade.late_charges import late_charge_check
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policies
from plantgraph.qa.cascade.report_groups import breakdown, question_groups
from plantgraph.qa.cascade.report_models import (
    CorpusReport,
    LateChargeCheck,
    NotEvaluated,
    PolicyResult,
    Report,
    Tier3Tally,
    Verdict,
)
from plantgraph.qa.cascade.report_references import acceptance_result, reference_fields
from plantgraph.qa.cascade.report_scopes import load_splits
from plantgraph.qa.cascade.report_sealed import build_sealed
from plantgraph.qa.cascade.report_sealed_models import SealedClaimsReport
from plantgraph.qa.cascade.report_sealed_views import SealedCorpus
from plantgraph.qa.cascade.report_verdicts import (
    CONFIRM_CORPUS,
    LABEL_VARIANTS,
    PRIMARY,
    RUNAWAY_TIER,
    TIER3_CANDIDATES,
    check_label_variant,
    check_latency_bound,
    confirm_cascade,
    select_tier3,
    tally_tier3,
)
from plantgraph.qa.cascade.report_verdicts_v2 import (
    CONFIRM_CORPUS_V3,
    SELECT_CORPUS,
    confirm_on_scale,
    select_on_dev,
)
from plantgraph.qa.models import Question
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph

ALWAYS_N = "always_n"
#: The always-one-tier baselines are part of every report, whatever `--policy` selects.
BASELINES = (ALWAYS_N, "always_c", "always_g")

#: corpus id -> tier name -> where that tier's stored run lives.
SourcesByCorpus = Mapping[str, Mapping[str, TierSource]]


def _policy_result(
    joined: JoinedCorpus, evaluation: Evaluation, always_n: Evaluation | None, bound: LatencyBound
) -> PolicyResult:
    """One policy's row: summary, acceptance, and (where defined) references and comparisons."""
    fields = reference_fields(joined, evaluation, bound.cutoff_s)
    if always_n is not None and joined.policy.name != ALWAYS_N:
        fields["vs_always_n"] = compare(evaluation.series(), always_n.series())
    fields |= {
        "summary": evaluation.summary,
        "latency_verdicts": check_latency_bound(evaluation.summary, bound),
        "acceptance": acceptance_result(joined),
    }
    return PolicyResult.model_validate(fields)


def _evaluate_all(
    corpus_id: str,
    policies: Sequence[CascadePolicy],
    sources: Mapping[str, TierSource],
    questions_root: Path,
    cutoff_s: float,
    find_anchors: AnchorFinder | None = None,
) -> tuple[dict[str, JoinedCorpus], dict[str, Evaluation], list[NotEvaluated]]:
    """Join every policy; evaluate those that are complete, list the others with the reason."""
    joins: dict[str, JoinedCorpus] = {}
    evaluations: dict[str, Evaluation] = {}
    problems: list[NotEvaluated] = []
    # a policy whose tiers record no need label (Cypher, agent) can borrow one from any stored run
    known_labels = labels_from_run_dirs(s.run_dir for s in sources.values())
    for policy in policies:
        try:
            joined = join_corpus(
                policy,
                dict(sources),
                corpus_id,
                questions_root,
                find_anchors=find_anchors,
                known_labels=known_labels,
            )
            joins[policy.name] = joined
            require_complete(joined)
            evaluations[policy.name] = evaluate_policy(joined, cutoff_s)
        except IncompleteJoinError as error:
            gaps = {tier: len(ids) for tier, ids in error.gaps.items()}
            problems.append(NotEvaluated(policy=policy.name, reason=str(error), gaps=gaps))
        except ValueError as error:  # refused join, or a need label the policy needs is missing
            problems.append(NotEvaluated(policy=policy.name, reason=str(error)))
    return joins, evaluations, problems


def _late_charges(
    joins: Mapping[str, JoinedCorpus], sources: Mapping[str, TierSource]
) -> list[LateChargeCheck]:
    """One check per (run, strategy) that some policy of this corpus reads and that timed out."""
    pairs = {
        (sources[tier.name].run_dir, tier.strategy)
        for joined in joins.values()
        for tier in joined.policy.tiers
        if tier.name in sources
    }
    checks = [late_charge_check(run_dir, strategy) for run_dir, strategy in sorted(pairs)]
    return [check for check in checks if check is not None]


def _corpus_report(
    corpus_id: str,
    questions: list[Question],
    joins: Mapping[str, JoinedCorpus],
    evaluations: Mapping[str, Evaluation],
    problems: list[NotEvaluated],
    bound: LatencyBound,
    sources: Mapping[str, TierSource],
    graph: ItemGraph | None,
) -> CorpusReport:
    always_n = evaluations.get(ALWAYS_N)
    results = [_policy_result(joins[name], ev, always_n, bound) for name, ev in evaluations.items()]
    # Each join takes need labels from its own runs' traces; the union covers every question.
    labels = {qid: lab for joined in joins.values() for qid, lab in joined.need_labels.items()}
    by_dimension = question_groups(questions, labels)
    by_id = {q.question_id: q for q in questions}
    return CorpusReport(
        corpus_id=corpus_id,
        n_questions=len(questions),
        policies=results,
        not_evaluated=problems,
        breakdowns={
            dimension: breakdown(evaluations, group_of, dimension)
            for dimension, group_of in by_dimension.items()
        },
        diagnostics=[
            policy_diagnostics(joins[name], ev, by_id, graph) for name, ev in evaluations.items()
        ],
        late_charges=_late_charges(joins, sources),
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


def _scale_verdicts(corpora: Sequence[CorpusReport], bound: LatencyBound) -> list[Verdict]:
    """V2 on D100 and V3 on D1000, from the policy summaries (INCOMPLETE if a corpus is absent)."""
    by_corpus = {c.corpus_id: {r.summary.policy: r.summary for r in c.policies} for c in corpora}
    selection = select_on_dev(by_corpus.get(SELECT_CORPUS, {}), bound)
    confirmation = confirm_on_scale(selection.chosen, by_corpus.get(CONFIRM_CORPUS_V3, {}), bound)
    return [selection.verdict, confirmation.verdict]


def _with_baselines(policies: Sequence[CascadePolicy] | None) -> list[CascadePolicy]:
    available = load_policies(POLICIES_DIR)
    chosen = {p.name: p for p in (available.values() if policies is None else policies)}
    for name in BASELINES:
        chosen.setdefault(name, available[name])
    return list(chosen.values())


def _sealed_corpus(
    corpus_id: str,
    questions: list[Question],
    questions_root: Path,
    corpora_root: Path,
    joins: Mapping[str, JoinedCorpus],
    evaluations: Mapping[str, Evaluation],
) -> SealedCorpus:
    """What the sealed tables need of one corpus: only the policies that could be evaluated."""
    return SealedCorpus(
        corpus_id=corpus_id,
        n_sheets=load_sheet_count(corpora_root, corpus_id),
        questions=questions,
        splits=load_splits(questions_root, corpus_id, questions),
        joins={name: joins[name] for name in evaluations},
        evaluations=evaluations,
    )


def build_report(
    corpus_ids: Sequence[str],
    sources: SourcesByCorpus,
    questions_root: Path,
    policies: Sequence[CascadePolicy] | None = None,
    bound: LatencyBound | None = None,
    corpora_root: Path | None = None,
    sealed_claims: bool = False,
) -> Report:
    """Evaluate `policies` (default: every policy file, plus the baselines) on each corpus.

    `bound` carries LB-1, LB-2 and the cutoff C applied to every arm alike (default 10/60/120 s).
    `corpora_root` (holding `<corpus>/ingest.json`) lets the report read each corpus's graph: for
    the isolation score, the named-tag diagnostic, and the rules labels of label-routed policies.
    `sealed_claims` swaps the dev rules S1-V3 for the sealed test's tables and claims (design
    `sealed-test-run.md` section 9); it needs explicit `policies` and a `corpora_root`.

    Raises:
        ValueError: `sealed_claims` without policies or without a corpora root.
    """
    bound = bound or LatencyBound()
    if sealed_claims and (not policies or corpora_root is None):
        raise ValueError(
            "expected --policy and --corpora-root with --sealed-claims, found one missing"
        )
    chosen = list(policies) if sealed_claims and policies else _with_baselines(policies)
    reports: list[CorpusReport] = []
    all_joins: dict[str, dict[str, JoinedCorpus]] = {}
    sealed_corpora: list[SealedCorpus] = []
    for corpus_id in corpus_ids:
        _, questions = load_questions_file(questions_root, corpus_id)
        view = None if corpora_root is None else load_corpus_view(corpora_root, corpus_id)
        joins, evaluations, problems = _evaluate_all(
            corpus_id,
            chosen,
            sources.get(corpus_id, {}),
            questions_root,
            bound.cutoff_s,
            None if view is None else anchor_finder(view),
        )
        all_joins[corpus_id] = joins
        graph = None if view is None else build_item_graph(view)
        reports.append(
            _corpus_report(
                corpus_id,
                questions,
                joins,
                evaluations,
                problems,
                bound,
                sources.get(corpus_id, {}),
                graph,
            )
        )
        if sealed_claims and corpora_root is not None:
            sealed_corpora.append(
                _sealed_corpus(
                    corpus_id, questions, questions_root, corpora_root, joins, evaluations
                )
            )
    if sealed_claims:
        return SealedClaimsReport(
            bound=bound,
            corpora=reports,
            tier3=[],
            verdicts=[],
            sealed=build_sealed(sealed_corpora, bound),
        )
    s1, tallies = _tier3_verdict(all_joins)
    verdicts = [s1, *_confirmation_verdicts(reports), *_scale_verdicts(reports, bound)]
    return Report(bound=bound, corpora=reports, tier3=tallies, verdicts=verdicts)
