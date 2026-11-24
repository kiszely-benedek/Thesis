"""The offline cascade per arm, on the toy tier runs of the cascade tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cascade_toy import CORPUS
from cascade_v4_toy import tier_sources
from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade.limits import SETTING_A
from plantgraph.qa.exp0009 import cascade_report as cr
from plantgraph.qa.need.labels import NeedLabel


@pytest.fixture(autouse=True)
def _no_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """The toy corpus has no graph; the first question is labelled first-valve."""
    monkeypatch.setattr(cr, "load_corpus_view", lambda root, corpus_id: None)
    monkeypatch.setattr(cr, "anchor_finder", lambda view: lambda text: Anchors())
    from plantgraph.qa.cascade import join

    monkeypatch.setattr(
        join,
        "classify_need",
        lambda text, finder: (
            NeedLabel.UPSTREAM_TO_FIRST_VALVE if "E-10-1" in text else NeedLabel.GENERIC
        ),
    )


def test_a2_report_counts_per_family(tmp_path: Path) -> None:
    sources = tier_sources(tmp_path, timeout_s=SETTING_A.cypher_timeout_s)
    report = cr.build_arm_report(CORPUS, "A2", sources, tmp_path / "questions", tmp_path)
    assert report.policy == "cascade_v4_iso" and report.n_questions == 4
    assert sum(t for _c, t in report.by_family.values()) == 4
    assert sum(c for c, _t in report.by_family.values()) == report.n_correct
    assert 0.0 <= report.accuracy() <= 1.0


def test_b_policy_reads_the_b_strategy_names() -> None:
    policy = cr.policy_of("B")
    assert policy.name == "cascade_v4_iso_b"
    assert all(t.strategy.endswith("_b") for t in policy.tiers)
    with pytest.raises(ValueError, match="arm"):
        cr.policy_of("C")  # type: ignore[arg-type]


def test_the_frozen_need_classifier_accepts_every_x_question_text() -> None:
    """The cascade routes by need label: it must not raise on the scope X texts (§19.12 6)."""
    from exp0009_small import built_small
    from test_records import two_runs

    from plantgraph.qa.cascade.corpus_checks import load_corpus_view
    from plantgraph.qa.cascade.labels import anchor_finder, classify_need

    spec, corpora, _record = built_small()
    finder = anchor_finder(load_corpus_view(corpora, spec.b_id))
    texts = [q.text for q in two_runs().b_questions]
    assert texts and all(classify_need(text, finder) is not None for text in texts)
