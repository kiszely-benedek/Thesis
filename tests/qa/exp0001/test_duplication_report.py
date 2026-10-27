"""cascade_v3 at three duplication rates: pairing by question stem."""

from __future__ import annotations

import pytest

from plantgraph.qa.exp0001.duplication_report import (
    build_duplication_report,
    pair_by_stem,
    parse_points,
    render_duplication_markdown,
    stem_of,
)
from plantgraph.qa.exp0001.report_models import QuestionScore
from plantgraph.qa.models import Outcome


def _score(qid: str, correct: bool) -> QuestionScore:
    return QuestionScore(
        qid=qid,
        family="CONNECTED",
        correct=correct,
        correct_at_cutoff=correct,
        cost_usd=0.001,
        latency_s=1.0,
        outcome=Outcome.ANSWERED,
    )


def _corpus(corpus_id: str, results: dict[str, bool]) -> list[QuestionScore]:
    return [_score(f"{corpus_id}:{stem}", ok) for stem, ok in results.items()]


def test_the_stem_is_the_id_without_the_corpus_prefix() -> None:
    assert stem_of("H100g2d0:CONNECTED:E-1|E-2", "H100g2d0") == "CONNECTED:E-1|E-2"
    with pytest.raises(ValueError, match="start with 'H100g2:'"):
        stem_of("H100g2d0:CONNECTED:E-1", "H100g2")


def test_only_common_stems_are_paired_and_the_rest_is_counted() -> None:
    low = _corpus("H100g2d0", {"a": True, "b": True, "c": True, "only_low": False})
    high = _corpus("H100g2d50", {"a": True, "b": False, "c": False, "only_high": True})
    pair = pair_by_stem(("H100g2d50", high), ("H100g2d0", low))
    assert (pair.n_common, pair.n_only_high, pair.n_only_low) == (3, 1, 1)
    assert pair.delta == pytest.approx(-2 / 3)  # high is right on 1 of 3, low on 3 of 3


def test_corpora_without_a_common_stem_are_refused() -> None:
    with pytest.raises(ValueError, match="share question stems"):
        pair_by_stem(("B", _corpus("B", {"x": True})), ("A", _corpus("A", {"y": True})))


def test_the_report_orders_points_by_rate_and_pairs_every_two() -> None:
    results = {"a": True, "b": False}
    scored = [
        ("H100g2d50", 50, _corpus("H100g2d50", results)),
        ("H100g2d0", 0, _corpus("H100g2d0", results)),
        ("H100g2", 25, _corpus("H100g2", results)),
    ]
    report = build_duplication_report(scored)
    assert [p.duplication_percent for p in report.points] == [0, 25, 50]
    assert [(q.high, q.low) for q in report.pairs] == [
        ("H100g2", "H100g2d0"),
        ("H100g2d50", "H100g2d0"),
        ("H100g2d50", "H100g2"),
    ]
    assert all(q.delta == 0.0 for q in report.pairs)
    text = render_duplication_markdown(report)
    assert "descriptive" in text and "H100g2d50 - H100g2d0" in text


def test_points_are_parsed_and_malformed_ones_refused() -> None:
    assert parse_points("A=0,B=25") == [("A", 0), ("B", 25)]
    with pytest.raises(ValueError, match="H100g2d0=0"):
        parse_points("A")
