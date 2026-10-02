"""API-02: how much of each question family the plant API can express (design §3.4).

For every question, the family's canonical program (`canonical_programs.py`) computes an answer
with no model; the check is whether it equals the question's reference answer. The share per
family is the API's coverage of that family.

Run on a corpus (free: no network, no Neo4j)::

    uv run python -m plantgraph.qa.harness.api_expressiveness --corpus-id H100 \
        --ingest-json data/corpora/H100/ingest.json --seed 0 --n-per-family 100
"""

from __future__ import annotations

import argparse
import random
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.canonical_programs import run_canonical_program
from plantgraph.qa.models import (
    AnswerType,
    AnswerValue,
    FinalAnswer,
    Outcome,
    Question,
    QuestionFamily,
)
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.plant_api.model import PlantApiError
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.scoring import score_answer


class FamilyExpressiveness(BaseModel):
    """How many of one family's questions the canonical program answered correctly."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    n_questions: int
    n_equal: int
    #: Questions where a primitive raised `PlantApiError` (counted as not equal).
    n_errors: int

    @property
    def share(self) -> float:
        """Equal outputs over questions; 1.0 means the API expresses the family fully."""
        return self.n_equal / self.n_questions if self.n_questions else 1.0


def output_equals_reference(question: Question, output: AnswerValue) -> bool:
    """Whether a program's output is the reference answer, by the same rules as model answers.

    A `TAG_PATH` must match the reference route exactly (a model's answer may be any valid
    route; a program has no excuse for a different one). `None` means "not present".
    """
    if question.answer_type is AnswerType.TAG_PATH and question.answerable:
        return output == question.reference
    answer = FinalAnswer(answer=output, not_present=output is None)
    return score_answer(question, Outcome.ANSWERED, answer).correct


def _verdict(graph: ItemGraph, question: Question) -> str:
    """`"equal"`, `"different"`, or `"error"` when a primitive rejected the program's call."""
    try:
        output = run_canonical_program(graph, question)
    except PlantApiError:
        return "error"
    return "equal" if output_equals_reference(question, output) else "different"


def evaluate_programs(
    questions: list[Question], graph: ItemGraph
) -> dict[QuestionFamily, FamilyExpressiveness]:
    """Run each question's canonical program and tally the verdicts per family."""
    verdicts: dict[QuestionFamily, Counter[str]] = defaultdict(Counter)
    for question in questions:
        verdicts[question.family][_verdict(graph, question)] += 1
    return {
        family: FamilyExpressiveness(
            family=family, n_questions=c.total(), n_equal=c["equal"], n_errors=c["error"]
        )
        for family, c in verdicts.items()
    }


def render_table(rows: dict[QuestionFamily, FamilyExpressiveness]) -> str:
    """A markdown table, one line per family."""
    lines = ["| family | questions | equal | errors | share |", "|---|---|---|---|---|"]
    for family, row in sorted(rows.items(), key=lambda pair: pair[0].value):
        lines.append(
            f"| {family.value} | {row.n_questions} | {row.n_equal} | {row.n_errors} "
            f"| {row.share:.3f} |"
        )
    return "\n".join(lines)


def sample_per_family(
    candidates: dict[QuestionFamily, list[Question]], n_per_family: int, seed: int
) -> list[Question]:
    """Up to `n_per_family` candidates of each family, drawn with a per-family seeded stream.

    Unlike the k-bin sampler this gives every family the same weight, so a small family's
    share is not drawn from three questions.
    """
    drawn: list[Question] = []
    for family, questions in candidates.items():
        pool = sorted(questions, key=lambda q: q.question_id)
        rng = random.Random(f"{seed}:{family.value}")
        drawn += rng.sample(pool, min(n_per_family, len(pool)))
    return drawn


def main(argv: list[str] | None = None) -> None:
    """Rebuild a corpus, sample its questions, run every canonical program, print the table."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.harness.api_expressiveness")
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--n-per-family", required=True, type=int, help="questions per family")
    args = parser.parse_args(argv)

    artifacts = load_corpus_artifacts(args.corpus_id, args.ingest_json)
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    if plant is None or manifest is None:
        raise ValueError(f"expected a synthetic corpus with ground truth, found {args.corpus_id!r}")
    candidates = all_candidates(
        plant, manifest, artifacts.gold.sheets, corpus_id=args.corpus_id, seed=args.seed
    )
    questions = sample_per_family(candidates, args.n_per_family, args.seed)
    view = NetworkxGraphView(artifacts.corpus_id, artifacts.localized_sheets, artifacts.resolution)
    print(render_table(evaluate_programs(questions, build_item_graph(view))))


if __name__ == "__main__":
    main()
