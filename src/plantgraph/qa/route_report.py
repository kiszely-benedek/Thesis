"""The free routing report: Hierarchical's 2x2, retrieval only (design §3.8, ROUTE-01).

Hierarchical has two route modes and two budget modes (ADR-0030). Which pair is best
is decided by measurement, and the measurement needs no model: for each question this
runs `Hierarchical.retrieve` and scores what it routed to against the gold evidence
(`harness/routing_gold.py`). No `UnitRouter` is passed, so a question with no anchor
fails retrieval and is counted as such, instead of costing a call. There is no chat
client anywhere in this module.

Run: `python -m plantgraph.qa.route_report --corpus ID ... --max-context-chars N ...
--sheet-hops H --out DIR`, writing `route_report.csv` and `route_report.md`.

Retrieval time is wall-clock, so that one column differs between runs; every other
column is a pure function of the corpus, the questions and the parameters.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plantgraph.qa.context_budget import BUDGET_MODES
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import GraphView, NetworkxGraphView
from plantgraph.qa.harness.gold import ROUTING_HIT_TRACE_KEY
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.routing_gold import (
    EVIDENCE_NODE_RECALL_TRACE_KEY,
    RELAXED_ROUTING_HIT_TRACE_KEY,
    RoutingGold,
    add_routing_metrics,
    build_routing_gold,
)
from plantgraph.qa.models import Question, RetrievalResult
from plantgraph.qa.questions.availability import k_bin_of
from plantgraph.qa.route_report_tables import (
    QuestionMeasure,
    build_report_rows,
    render_csv,
    render_markdown,
)
from plantgraph.qa.sheet_selection import ROUTE_MODES
from plantgraph.qa.strategies.hierarchical import Hierarchical

CSV_FILENAME = "route_report.csv"
MARKDOWN_FILENAME = "route_report.md"

Clock = Callable[[], float]


def measure_corpus(
    corpus_id: str,
    view: GraphView,
    routing_gold: RoutingGold,
    questions: Sequence[Question],
    *,
    max_context_chars_values: Sequence[int],
    sheet_hops: int,
    clock: Clock = time.perf_counter,
) -> list[QuestionMeasure]:
    """Retrieve every question under every budget and route x budget combination.

    `clock` is injectable so a test can make the timing column deterministic.
    """
    measures: list[QuestionMeasure] = []
    for max_chars in max_context_chars_values:
        for route_mode in ROUTE_MODES:
            for budget_mode in BUDGET_MODES:
                setting = _Setting(corpus_id, max_chars, route_mode, budget_mode)
                strategy = Hierarchical(
                    view,
                    route_mode=route_mode,
                    budget_mode=budget_mode,
                    sheet_hops=sheet_hops,
                    max_context_chars=max_chars,
                )
                measures += [
                    _measure_question(strategy, question, setting, routing_gold, clock)
                    for question in questions
                ]
    return measures


@dataclass(frozen=True)
class _Setting:
    """Which corpus, budget and combination a retrieval ran under."""

    corpus_id: str
    max_context_chars: int
    route_mode: str
    budget_mode: str


def _measure_question(
    strategy: Hierarchical,
    question: Question,
    setting: _Setting,
    routing_gold: RoutingGold,
    clock: Clock,
) -> QuestionMeasure:
    """One retrieval, scored against the gold evidence."""
    started = clock()
    result = strategy.retrieve(question.text)
    elapsed_ms = (clock() - started) * 1000
    trace: dict[str, Any] = {"retrieval": result.trace}
    add_routing_metrics(trace, question, routing_gold)  # same code path as a live run
    return QuestionMeasure(
        corpus_id=setting.corpus_id,
        max_context_chars=setting.max_context_chars,
        route_mode=setting.route_mode,
        budget_mode=setting.budget_mode,
        question_id=question.question_id,
        family=question.family.value,
        k_bin=k_bin_of(question).value,
        u=question.u,
        strict_hit=trace.get(ROUTING_HIT_TRACE_KEY),
        relaxed_hit=trace.get(RELAXED_ROUTING_HIT_TRACE_KEY),
        node_recall=trace.get(EVIDENCE_NODE_RECALL_TRACE_KEY),
        retrieval_failed=result.context is None,
        context_chars=_context_chars(result),
        over_budget=result.trace.get("over_budget"),
        route_fallback=_route_fallback(result),
        retrieval_ms=elapsed_ms,
    )


def _context_chars(result: RetrievalResult) -> int | None:
    return None if result.context is None else len(result.context)


def _route_fallback(result: RetrievalResult) -> bool | None:
    """`None` when retrieval failed before routing; else whether the flow search fell back."""
    if "route_fallback" not in result.trace:
        return None
    return result.trace["route_fallback"] is not None


def load_view_and_gold(corpus_id: str, corpora_root: Path) -> tuple[GraphView, RoutingGold]:
    """Rebuild a corpus from its `ingest.json`: the strategies' view and the gold side."""
    artifacts = load_corpus_artifacts(corpus_id, corpora_root / corpus_id / "ingest.json")
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    if plant is None or manifest is None:
        raise ValueError(
            f"expected a ground-truth plant and manifest for {corpus_id!r}, found none"
        )
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    gold = build_routing_gold(plant, artifacts.gold.sheets, manifest, artifacts.gold.occurrence_map)
    return view, gold


def write_report(measures: list[QuestionMeasure], out_dir: Path) -> tuple[Path, Path]:
    """Write the CSV and the markdown summary into `out_dir`; return both paths."""
    rows = build_report_rows(measures)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, markdown_path = out_dir / CSV_FILENAME, out_dir / MARKDOWN_FILENAME
    csv_path.write_text(render_csv(rows), encoding="utf-8", newline="")
    markdown_path.write_text(render_markdown(rows), encoding="utf-8", newline="")
    return csv_path, markdown_path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m plantgraph.qa.route_report", description=__doc__
    )
    parser.add_argument("--corpus", action="append", required=True, help="corpus id; repeatable")
    parser.add_argument("--max-context-chars", type=int, nargs="+", required=True)
    parser.add_argument("--sheet-hops", type=int, required=True, help="rings around the route")
    parser.add_argument("--corpora-root", type=Path, default=Path("data") / "corpora")
    parser.add_argument("--questions-root", type=Path, default=Path("data") / "questions")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Measure every corpus given, write the report, print where it went."""
    args = _parse_args(argv)
    measures: list[QuestionMeasure] = []
    for corpus_id in args.corpus:
        view, gold = load_view_and_gold(corpus_id, args.corpora_root)
        questions = load_questions(questions_path(args.questions_root, corpus_id), corpus_id)
        measures += measure_corpus(
            corpus_id,
            view,
            gold,
            questions,
            max_context_chars_values=args.max_context_chars,
            sheet_hops=args.sheet_hops,
        )
    csv_path, markdown_path = write_report(measures, args.out)
    print(f"wrote {csv_path} and {markdown_path} ({len(measures)} retrievals)")


if __name__ == "__main__":
    main()
