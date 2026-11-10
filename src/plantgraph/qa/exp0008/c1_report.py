"""The concurrency-1 control (descriptive): does running 4 questions at once change answers?

    python -m plantgraph.qa.exp0008.c1_report --main-answers A.jsonl \
        --control-answers B.jsonl --out R.md

The control reruns a subset of the main run's questions one at a time. This report compares, on
the questions both runs answered, the number correct, how often the per-question verdict agrees,
and the latency median and 90th percentile (the figures R5 quoted by hand).
"""

from __future__ import annotations

import argparse
import statistics
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.models import QuestionResult


class ControlComparison(BaseModel):
    """Main run against control run on the control's questions."""

    model_config = ConfigDict(frozen=True)

    n_questions: int
    main_correct: int
    control_correct: int
    verdicts_agree: int
    main_latency_median_s: float
    main_latency_p90_s: float
    control_latency_median_s: float
    control_latency_p90_s: float


def read_results(answers_path: Path) -> dict[str, QuestionResult]:
    """The rows of an `answers.jsonl` by question id.

    Raises:
        ValueError: a question appears twice (the control compares one answer per question).
    """
    rows: dict[str, QuestionResult] = {}
    for line in answers_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = QuestionResult.model_validate_json(line)
        if row.question_id in rows:
            raise ValueError(
                f"expected one row per question in {answers_path}, found {row.question_id} twice"
            )
        rows[row.question_id] = row
    return rows


def _p90(values: list[float]) -> float:
    return (
        statistics.quantiles(values, n=10, method="inclusive")[-1] if len(values) > 1 else values[0]
    )


def compare(
    main: dict[str, QuestionResult], control: dict[str, QuestionResult]
) -> ControlComparison:
    """Compare the two runs on the questions the control holds.

    Raises:
        ValueError: the control is empty, or holds a question the main run lacks.
    """
    if not control:
        raise ValueError("expected a control run with at least one row, found none")
    missing = sorted(set(control) - set(main))
    if missing:
        raise ValueError(f"expected every control question in the main run, missing {missing[:3]}")
    pairs = [(main[qid], control[qid]) for qid in sorted(control)]
    main_latency = [m.latency_s for m, _ in pairs]
    control_latency = [c.latency_s for _, c in pairs]
    return ControlComparison(
        n_questions=len(pairs),
        main_correct=sum(m.correct for m, _ in pairs),
        control_correct=sum(c.correct for _, c in pairs),
        verdicts_agree=sum(m.correct == c.correct for m, c in pairs),
        main_latency_median_s=statistics.median(main_latency),
        main_latency_p90_s=_p90(main_latency),
        control_latency_median_s=statistics.median(control_latency),
        control_latency_p90_s=_p90(control_latency),
    )


def render(result: ControlComparison) -> str:
    """The comparison as the short markdown the reports folder keeps."""
    return (
        "# Concurrency-1 control (agent tier, descriptive)\n\n"
        f"On the {result.n_questions} questions of the control:\n\n"
        "| | main run (concurrency 4) | control (concurrency 1) |\n|---|---|---|\n"
        f"| correct | {result.main_correct} | {result.control_correct} |\n"
        f"| latency median, s | {result.main_latency_median_s:.1f} | "
        f"{result.control_latency_median_s:.1f} |\n"
        f"| latency p90, s | {result.main_latency_p90_s:.1f} | "
        f"{result.control_latency_p90_s:.1f} |\n\n"
        f"The per-question verdict agrees on {result.verdicts_agree} of {result.n_questions}.\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Write the report; returns the exit status."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0008.c1_report")
    parser.add_argument("--main-answers", type=Path, required=True)
    parser.add_argument("--control-answers", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = compare(read_results(args.main_answers), read_results(args.control_answers))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(result), encoding="utf-8")
    print(f"control report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
