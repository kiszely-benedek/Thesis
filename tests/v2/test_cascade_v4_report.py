"""QT-6: the V2T tuning report over toy stored runs, under both limit settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cascade_toy import CORPUS
from cascade_v4_toy import tier_sources
from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade import join, tune_report
from plantgraph.qa.cascade.limits import SETTING_A, SETTING_B, LimitSetting
from plantgraph.qa.cascade.tune_compare import family_changes, regressed_families
from plantgraph.qa.cascade.tune_models import CypherAcceptance, TuneReport
from plantgraph.qa.cascade.tune_render import render_tune_report
from plantgraph.qa.cascade.tune_report import build_tune_report
from plantgraph.qa.cascade.tune_select import V4, V4_ISO
from plantgraph.qa.need.labels import NeedLabel


@pytest.fixture
def _no_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ingest.json: the toy corpus has no graph. The first question is labelled first-valve."""
    monkeypatch.setattr(tune_report, "load_corpus_view", lambda root, corpus_id: None)
    monkeypatch.setattr(tune_report, "anchor_finder", lambda view: lambda text: Anchors())
    monkeypatch.setattr(
        join,
        "classify_need",
        lambda text, finder: (
            NeedLabel.UPSTREAM_TO_FIRST_VALVE if "E-10-1" in text else NeedLabel.GENERIC
        ),
    )


def _report(tmp_path: Path, setting: LimitSetting) -> Any:
    sources = tier_sources(tmp_path, timeout_s=setting.cypher_timeout_s)
    return build_tune_report(CORPUS, setting, sources, tmp_path / "questions", tmp_path)


@pytest.mark.usefixtures("_no_corpus")
def test_setting_a_scores_the_130_s_answer_as_late_but_uncut_counts_it(tmp_path: Path) -> None:
    report = _report(tmp_path, SETTING_A)

    v4 = report.results[V4]
    # q1 Cypher, q2 agent (Cypher was cut), q4 agent after 130 s; q3 wrong in both tiers
    assert v4.n_questions == 4 and v4.n_correct_uncut == 3
    assert v4.n_beyond_limit == 1 and v4.n_correct_in_limit == 2
    assert v4.n_correct_within == {"120": 2, "300": 3}
    assert report.oracle_correct == 3 and report.cypher.n_cut_but_correct == 1


@pytest.mark.usefixtures("_no_corpus")
def test_setting_b_has_no_deadline_below_the_hang_guard(tmp_path: Path) -> None:
    report = _report(tmp_path, SETTING_B)

    v4 = report.results[V4]
    assert v4.n_correct_uncut == 3 and v4.n_correct_in_limit == 3 and v4.n_beyond_limit == 0


@pytest.mark.usefixtures("_no_corpus")
def test_the_report_counts_what_the_accept_rule_rejected(tmp_path: Path) -> None:
    cypher = _report(tmp_path, SETTING_A).cypher

    assert (cypher.n_tried, cypher.n_accepted, cypher.n_accepted_correct) == (4, 1, 1)
    assert cypher.rejected_by == {"complete": 1, "answered": 1, "not_abstained": 1}


@pytest.mark.usefixtures("_no_corpus")
def test_the_iso_variant_sends_first_valve_questions_to_the_agent(tmp_path: Path) -> None:
    report = _report(tmp_path, SETTING_A)

    iso = report.results[V4_ISO]
    assert iso.n_correct_uncut == 2  # q1 now goes to the agent, which is wrong on it
    assert report.choice is None  # the rule is defined on the tuning set only
    assert report.results[V4].by_family["CONNECTED"].total == 4


@pytest.mark.usefixtures("_no_corpus")
def test_the_report_renders_the_primary_and_secondary_numbers(tmp_path: Path) -> None:
    report = _report(tmp_path, SETTING_A)
    current = report.model_copy()
    previous = report.model_copy(
        update={"results": {**report.results, V4: _with_correct(report.results[V4], 4)}}
    )

    changes = family_changes(current, previous, V4)
    text = render_tune_report(report, changes)

    assert "setting A" in text and "acc@120" in text and "acc@300" in text
    assert "| cascade_v4 | 3/4 | 2/4 | 3/4 |" in text
    assert regressed_families(changes, min_drop=1) == ["CONNECTED"]
    assert regressed_families(changes, min_drop=2) == []


def _with_correct(result: Any, correct: int) -> Any:
    family = result.by_family["CONNECTED"].model_copy(update={"correct": correct})
    return result.model_copy(update={"by_family": {"CONNECTED": family}})


def test_comparing_rounds_of_different_settings_is_refused(tmp_path: Path) -> None:
    a = _fake_report(SETTING_A)
    b = _fake_report(SETTING_B)

    with pytest.raises(ValueError, match="same corpus and setting"):
        family_changes(a, b, V4)


def _fake_report(setting: LimitSetting) -> Any:
    return TuneReport(
        corpus_id=CORPUS,
        setting=setting,
        n_questions=0,
        oracle_correct=0,
        results={},
        cypher=CypherAcceptance(
            n_tried=0, n_accepted=0, n_accepted_correct=0, rejected_by={}, n_cut_but_correct=0
        ),
        choice=None,
    )
