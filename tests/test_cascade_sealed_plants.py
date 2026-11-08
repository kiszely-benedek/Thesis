"""The sealed report with several plants per scale: per-plant rows, pooled rows, robustness."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.exp0004 import e2e_report
from plantgraph.qa.cascade import cli
from plantgraph.qa.cascade.evaluate import LatencyBound
from plantgraph.qa.cascade.report_sealed import build_sealed
from plantgraph.qa.cascade.report_sealed_models import SealedReport
from plantgraph.qa.cascade.report_sealed_render import sealed_lines
from plantgraph.qa.cascade.report_sealed_views import group_scales
from test_cascade_sealed_report import PRIMARY, TIER2, _toy_corpus

SCALES = {"S100": ["A1", "A2"], "S1000": ["B1", "B2"]}


@pytest.fixture
def pooled(tmp_path: Path) -> SealedReport:
    plants = [
        _toy_corpus(tmp_path / name, name, sheets, None)
        for name, sheets in (("A1", 98), ("A2", 102), ("B1", 990), ("B2", 1010))
    ]
    return build_sealed(plants, LatencyBound(), scales=SCALES)


def test_scale_labels_replace_corpus_ids_in_the_claims_frame(pooled: SealedReport) -> None:
    assert (pooled.small_corpus, pooled.claims_corpus) == ("S100", "S1000")
    assert pooled.sheets == {"S100": 100, "S1000": 1000}  # the mean realized count per scale
    assert pooled.scales == SCALES


def test_each_plant_keeps_its_own_rows_and_the_pooled_row_follows(pooled: SealedReport) -> None:
    ids = [r.corpus_id for r in pooled.scope_rows if r.policy == PRIMARY]

    assert set(ids) == {"A1", "A2", "B1", "B2", "S100", "S1000"}
    assert ids.index("S100") > ids.index("A2")  # per plant first, then pooled
    row = next(r for r in pooled.scope_rows if (r.corpus_id, r.policy) == ("S1000", PRIMARY))
    assert row.summary.n_questions == 6  # 3 headline questions on each of two plants


def test_paired_claims_have_per_plant_and_pooled_rows(pooled: SealedReport) -> None:
    q5 = [r for r in pooled.paired_rows if r.claim == "Q5" and r.policy == TIER2]

    assert {r.corpus_id for r in q5} == {"A1", "A2", "B1", "B2", "S100", "S1000"}


def test_scale_rows_pool_both_scales_and_count_plants(pooled: SealedReport) -> None:
    row = next(r for r in pooled.scale_rows if r.policy == PRIMARY)

    assert (row.small_corpus, row.large_corpus) == ("S100", "S1000")
    assert (row.n_plants_small, row.n_plants_large) == (2, 2)
    assert row.accuracy_diff.ci_low <= row.accuracy_diff.estimate <= row.accuracy_diff.ci_high


def test_the_claims_are_judged_on_the_pooled_large_scale(pooled: SealedReport) -> None:
    by_rule = {v.rule: v.status for v in pooled.claims}

    # K1/Q5/K3 find their pair or row under the pooled label, so none is INCOMPLETE
    assert {by_rule["K1"], by_rule["Q5"], by_rule["K3"]} <= {"PASS", "FAIL"}


def test_robustness_counts_plants_and_is_rendered(pooled: SealedReport) -> None:
    claims = {r.claim for r in pooled.robustness}

    assert {"K1", "Q5", "Q4"} <= claims
    assert all(0 <= r.n_same_sign <= r.n_plants == 2 for r in pooled.robustness)
    text = "\n".join(sealed_lines(pooled, LatencyBound()))
    assert "Plant robustness (descriptive, not judged)" in text
    assert any("two-stage cluster bootstraps" in note for note in pooled.notes)


def test_a_corpus_in_two_scales_is_refused(tmp_path: Path) -> None:
    corpora = [_toy_corpus(tmp_path / n, n, 10, None) for n in ("A1", "A2")]

    with pytest.raises(ValueError, match="belong to one scale"):
        group_scales(corpora, {"X": ["A1"], "Y": ["A1", "A2"]})


def test_an_unknown_corpus_in_a_scale_is_refused(tmp_path: Path) -> None:
    corpora = [_toy_corpus(tmp_path / "A1", "A1", 10, None)]

    with pytest.raises(ValueError, match="exist in"):
        group_scales(corpora, {"X": ["A1", "nope"]})


def test_scale_option_is_parsed_into_label_and_plants() -> None:
    assert cli._parse_scales(["S1000=B1,B2", "S100=A1"]) == {"S1000": ["B1", "B2"], "S100": ["A1"]}
    with pytest.raises(SystemExit, match="expected --scale LABEL"):
        cli._parse_scales(["S1000"])


def test_plant_option_of_the_e2e_report_defaults_to_the_first_measurement() -> None:
    assert e2e_report._parse_plants([]) == [("H1000g2", "H1000g2V")]
    assert e2e_report._parse_plants(["H1000g21p1:H1000g21p1V"]) == [("H1000g21p1", "H1000g21p1V")]
    with pytest.raises(SystemExit, match="expected --plant"):
        e2e_report._parse_plants(["H1000g21p1"])
