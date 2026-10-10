"""How well the gold-free answer sheets match the true evidence sheets of a recorded run.

This is evaluation-side code: it reads each question's gold `evidence_sheets`, which the
demo's decision and display code (`evidence.py`) never does. It measures how far the
sheets shown to a user would match the sheets a question really depends on.
Run it as `python -m plantgraph.demo.app.agreement --run-dir ... --strategy ...`.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.demo.app.evidence import answer_tags, sheets_by_tag
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.models import Question, QuestionResult
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.scoring import normalize_scalar


class AgreementReport(BaseModel):
    """Precision and recall of the answer sheets against gold, averaged over questions."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    strategy: str
    #: Answered questions that have gold evidence sheets.
    n_questions: int
    #: Of those, questions for which any answer sheet was found (precision is defined there).
    n_with_sheets: int
    #: Mean over questions with answer sheets: share of shown sheets that are gold.
    precision: float
    #: Mean over all counted questions: share of gold sheets that are shown.
    recall: float


def evidence_sheet_agreement(
    run_dir: Path, strategy: str, questions: Sequence[Question], item_graph: ItemGraph
) -> AgreementReport:
    """Compare the answer sheets of every answered row of `strategy` with gold.

    Raises:
        ValueError: the run has no answered row of `strategy` with gold evidence sheets.
    """
    by_id = {q.question_id: q for q in questions}
    rows = [r for r in RunDir(run_dir).read_rows() if r.strategy == strategy]
    scores = [
        _score(by_id[row.question_id], row, item_graph)
        for row in rows
        if row.final_answer is not None and by_id[row.question_id].evidence_sheets
    ]
    if not scores:
        raise ValueError(f"expected answered rows with evidence sheets in {run_dir}, found none")
    precisions = [p for p, _ in scores if p is not None]
    return AgreementReport(
        run_id=run_dir.name,
        strategy=strategy,
        n_questions=len(scores),
        n_with_sheets=len(precisions),
        precision=sum(precisions) / len(precisions) if precisions else 0.0,
        recall=sum(r for _, r in scores) / len(scores),
    )


def _score(
    question: Question, row: QuestionResult, item_graph: ItemGraph
) -> tuple[float | None, float]:
    """(precision, recall) of one question; precision is `None` when no sheet was shown."""
    tags = answer_tags(question.text, question.answer_type, row.final_answer, item_graph)
    shown = {normalize_scalar(sheet) for sheet in sheets_by_tag(tags, item_graph)}
    gold = {normalize_scalar(sheet) for sheet in question.evidence_sheets}
    hits = len(shown & gold)
    return (hits / len(shown) if shown else None), hits / len(gold)


def _format(report: AgreementReport) -> str:
    return (
        f"{report.run_id} [{report.strategy}]: {report.n_questions} questions, "
        f"{report.n_with_sheets} with answer sheets; "
        f"precision {report.precision:.3f}, recall {report.recall:.3f}"
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Print the agreement of one run for the corpus the run was made on."""
    from plantgraph.qa.corpus import load_corpus_artifacts
    from plantgraph.qa.graph_view import NetworkxGraphView
    from plantgraph.qa.harness.question_set import load_questions, questions_path
    from plantgraph.qa.plant_api.item_graph import build_item_graph

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--corpora-root", type=Path, default=Path("data/runs/cv1/corpora"))
    parser.add_argument("--questions-root", type=Path, default=Path("data/runs/cv1/questions"))
    args = parser.parse_args(argv)
    artifacts = load_corpus_artifacts(args.corpus, args.corpora_root / args.corpus / "ingest.json")
    view = NetworkxGraphView(args.corpus, artifacts.localized_sheets, artifacts.resolution)
    questions = load_questions(questions_path(args.questions_root, args.corpus), args.corpus)
    print(
        _format(
            evidence_sheet_agreement(args.run_dir, args.strategy, questions, build_item_graph(view))
        )
    )


if __name__ == "__main__":
    main()
