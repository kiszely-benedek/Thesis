"""Report-side checks that read the corpus's item graph (evaluation side, never a policy).

Two checks need to know what an answer or a trace refers to, not only whether it was right:
the secondary isolation score (U4) and the "named tags never touched" count (D1, in
`diagnostics.py`). Both read the plant's item graph, the same graph the agent's tools query.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from plantgraph.qa.cascade.evaluate import Evaluation
from plantgraph.qa.cascade.join import JoinedCorpus
from plantgraph.qa.cascade.report_models import Cell, IsolationScores
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.models import AnswerValue, Outcome, Question, QuestionFamily
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.scoring import normalize_scalar, score_set


def load_item_graph(corpora_root: Path, corpus_id: str) -> ItemGraph:
    """The corpus's item graph, rebuilt from its stored ingest result (as `agreement.py` does)."""
    ingest_json = corpora_root / corpus_id / "ingest.json"
    artifacts = load_corpus_artifacts(corpus_id, ingest_json)
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    return build_item_graph(view)


def control_valve_tags(graph: ItemGraph) -> frozenset[str]:
    """Folded tags of the control valves: items some actuator drives with a `control` edge.

    ADR-0044: `actuator -control-> valve`, so a control valve is the target of a `control`
    edge. A valve nothing drives (a hand valve, a check valve) is not one.
    """
    driven = {edge.target for edge in graph.edges if edge.relation == "control"}
    tags = (graph.item(item_id).tag for item_id in driven)
    return frozenset(normalize_scalar(tag) for tag in tags if tag is not None)


def _tags_of(answer: AnswerValue) -> list[str]:
    if isinstance(answer, list):
        return [str(tag) for tag in answer]
    return [] if answer is None else [str(answer)]


def _is_correct_against(
    reference: list[str], joined: JoinedCorpus, question_id: str, answered_by: str | None
) -> bool:
    """Whether the decision's final answer equals `reference` as a tag set."""
    if answered_by is None:
        return False
    row = joined.runs[answered_by].rows[question_id]
    if row.outcome is not Outcome.ANSWERED or row.final_answer is None:
        return False
    if row.final_answer.not_present:
        return False
    return score_set(reference, _tags_of(row.final_answer.answer)).correct


def _without(control_tags: frozenset[str], tags: list[str]) -> list[str]:
    return [tag for tag in tags if normalize_scalar(tag) not in control_tags]


def isolation_scores(
    joined: JoinedCorpus,
    evaluation: Evaluation,
    questions: Mapping[str, Question],
    control_tags: frozenset[str],
) -> IsolationScores | None:
    """Primary and "control valves do not isolate" scores over UPSTREAM_ISOLATION questions.

    The secondary reference is the gold tag set minus every control valve (see
    `control_valve_tags`); an answer is correct against it on an exact set match. A question
    whose gold holds only control valves has no alternative reference and is left out of the
    secondary cell. Returns `None` when the corpus has no UPSTREAM_ISOLATION question.
    """
    primary = [0, 0]
    secondary = [0, 0]
    for scored in evaluation.scored:
        decision = scored.decision
        question = questions[decision.question_id]
        if question.family is not QuestionFamily.UPSTREAM_ISOLATION:
            continue
        primary[0] += scored.correct
        primary[1] += 1
        reference = [
            t for t in _tags_of(question.reference) if normalize_scalar(t) not in control_tags
        ]
        if not reference:
            continue
        secondary[1] += 1
        secondary[0] += _is_correct_against(
            reference, joined, decision.question_id, decision.answered_by
        )
    if primary[1] == 0:
        return None
    return IsolationScores(
        primary=Cell(correct=primary[0], total=primary[1]),
        control_valves_excluded=Cell(correct=secondary[0], total=secondary[1]),
    )
