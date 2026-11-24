"""The T17 claims on synthetic sealed roots: known answers give known values."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_analysis_fixtures import Recipe, build_exp0008_root, build_root

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade import join
from plantgraph.qa.cascade.stats_cluster import cluster_unpaired_bootstrap
from plantgraph.qa.exp0009.analysis import build_report
from plantgraph.qa.exp0009.analysis_models import AnalysisReport, ClaimRow, ClaimStatus, Table
from plantgraph.qa.need.labels import NeedLabel

#: A2 loses 4 of 20 R questions at 1,000 sheets; B loses 2 more than A2 at 100 sheets
DEGRADED = Recipe(a2_r={100: 20, 1000: 16}, b_r={100: 18, 1000: 16})
#: nothing changes with scale: every difference is exactly 0, so an interval is [0, 0]
FLAT = Recipe(a2_r={100: 20, 1000: 20}, b_r={100: 20, 1000: 20})


def _finder(_corpus_id: str) -> object:
    return lambda _text: Anchors()


def _report(root: Path, exp0008: Path | None = None) -> AnalysisReport:
    """The analysis with the toy corpus's missing graph stood in for (every question is GENERIC)."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(join, "classify_need", lambda text, finder: NeedLabel.GENERIC)
        return build_report(root, exp0008 or root / "no-exp0008", _finder, _finder)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def degraded(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, AnalysisReport]:
    root = build_root(tmp_path_factory.mktemp("degraded") / "root", DEGRADED)
    exp0008 = build_exp0008_root(tmp_path_factory.mktemp("v21") / "exp0008", {100: 18, 1000: 18})
    return root, _report(root, exp0008)


def claim(report: AnalysisReport, name: str) -> ClaimRow:
    return next(c for c in report.claims if c.claim == name)


def table(report: AnalysisReport, name: str) -> Table:
    return next(t for t in report.tables if t.name == name)


def row_of(tbl: Table, *start: object) -> list[object]:
    """The table row that begins with these cells."""
    return next(r for r in tbl.rows if tuple(r[: len(start)]) == start)


def test_q4_is_s1000_minus_s100_and_fails_when_the_interval_is_below_zero(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    q4 = claim(degraded[1], "Q4")
    assert q4.status is ClaimStatus.FAIL and q4.interval is not None
    assert q4.interval.estimate == pytest.approx(-0.2)  # 16/20 against 20/20, 20 counted per plant
    assert q4.interval.ci_high < 0
    assert q4.n_questions == 4 * 20  # the 2 LOOP and 2 held-out-wording questions stay out


def test_q4_is_the_cluster_bootstrap_of_the_known_flags(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    small = [[1.0] * 20, [1.0] * 20]
    large = [[1.0] * 16 + [0.0] * 4, [1.0] * 16 + [0.0] * 4]
    expected = cluster_unpaired_bootstrap(small, large, lambda s, g: g - s)
    q4 = claim(degraded[1], "Q4")
    assert q4.interval is not None
    assert (q4.interval.estimate, q4.interval.ci_low, q4.interval.ci_high) == pytest.approx(
        (expected.estimate, expected.ci_low, expected.ci_high)
    )


def test_q4_passes_at_the_boundary_where_the_interval_is_exactly_zero(tmp_path: Path) -> None:
    report = _report(build_root(tmp_path / "flat", FLAT))
    q4 = claim(report, "Q4")
    assert q4.interval is not None
    assert (q4.interval.ci_low, q4.interval.ci_high) == (0.0, 0.0)
    assert q4.status is ClaimStatus.PASS


def test_the_k_claims_and_q5_come_from_exp0008s_own_code(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    report = degraded[1]
    q5, k1, k3 = claim(report, "Q5"), claim(report, "K1"), claim(report, "K3")
    assert q5.status is ClaimStatus.PASS and q5.interval is not None  # agent 1.0, Cypher 0.8
    assert q5.interval.estimate == pytest.approx(0.2)
    assert k1.status is ClaimStatus.FAIL  # the cascade answers like the Cypher tier: it loses 0.2
    assert k3.unit == "seconds" and k3.status is ClaimStatus.PASS
    assert {c.claim for c in report.claims} >= {"K1", "K2", "K3", "Q5"}
    assert any("Q4 (primary)" in line for line in report.exp0008_verdicts)


def test_q4_b_pools_r_and_x_and_the_sensitivity_row_drops_position(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    q4b = claim(degraded[1], "Q4-B")
    assert q4b.interval is not None
    assert q4b.interval.ci_low < 0 < q4b.interval.ci_high and q4b.status is ClaimStatus.PASS
    # per plant 20 R + 4 isolation + 4 POSITION; B gets 18+4+2 right at 100 and 16+4+2 at 1,000
    assert q4b.interval.estimate == pytest.approx(22 / 28 - 24 / 28)
    sensitivity = claim(degraded[1], "Q4-B sensitivity (no POSITION_OF_VALVE)")
    assert sensitivity.interval is not None
    assert sensitivity.interval.estimate == pytest.approx(20 / 24 - 22 / 24)


def test_sb1_is_descriptive_and_sb2_must_lie_above_zero(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    report = degraded[1]
    sb1, sb2 = claim(report, "SB1"), claim(report, "SB2")
    assert sb1.status is ClaimStatus.DESCRIPTIVE and sb1.interval is not None
    assert sb1.interval.estimate == pytest.approx(-0.05)  # -0.1 at 100 sheets, 0 at 1,000
    assert claim(report, "SB1 S100").interval is not None
    assert sb2.status is ClaimStatus.PASS and sb2.interval is not None
    assert (sb2.interval.estimate, sb2.n_questions) == (1.0, 16)  # B right on 4/4, A2 on 0/4


def test_every_claim_names_run_folders_that_exist(degraded: tuple[Path, AnalysisReport]) -> None:
    root, report = degraded
    judged = [c for c in report.claims if not c.claim.startswith("Data effect")]
    assert all(c.runs for c in judged)
    assert all((root / "p1c" / "runs" / run).is_dir() for c in judged for run in c.runs)
    assert len(claim(report, "Q4").runs) == 4 * 2  # four plants, two tiers


def test_the_data_effect_is_v22_minus_v21_per_scale_on_shared_families(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    small, large = claim(degraded[1], "Data effect S100"), claim(degraded[1], "Data effect S1000")
    assert small.status is ClaimStatus.DESCRIPTIVE and small.interval is not None
    assert small.interval.estimate == pytest.approx(1.0 - 18 / 20)
    assert large.interval is not None and large.interval.estimate == pytest.approx(
        16 / 20 - 18 / 20
    )
    assert small.n_questions == 4 * 20  # two v2.2 and two v2.1 plants, 20 questions each


def test_position_accuracy_sits_beside_both_baselines(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    position = table(degraded[1], "position")
    tag = row_of(position, "both scales", "form: tag")
    assert tag[2:] == [12, pytest.approx(2 / 3), pytest.approx(2 / 3), pytest.approx(1.0)]
    code = row_of(position, "both scales", "code: NC")  # gold NC twice per plant
    assert code[2] == 8 and code[4] == 0.0  # the majority code NO is never right on NC


def test_named_by_refused_and_network_shares(degraded: tuple[Path, AnalysisReport]) -> None:
    report = degraded[1]
    assert row_of(table(report, "named_by"), "both scales")[1:4] == [16, 12, 4]
    refused = row_of(table(report, "x_refused"), "S100", "OPEN_VALVES_TO_ISOLATE")
    assert refused[2:] == [24, 2, 2, pytest.approx(4 / 24), 20]
    network = row_of(table(report, "network_touching"), "S1000", "R", "all")
    assert network[3:5] == [40, 2]  # one counted R question per plant carries a network tag
    assert row_of(table(report, "network_touching"), "S1000", "X", "all")[4] == 0


def test_x_subscopes_split_by_untagged_gold_and_discriminating(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    subscopes = table(degraded[1], "x_subscopes")
    untagged = row_of(subscopes, "both scales", "untagged gold")
    assert untagged[2:] == [8, 1.0, 0.0]  # 2 of 4 questions per plant; B right, A2 wrong
    assert row_of(subscopes, "both scales", "discriminating")[2] == 8


def test_rules_and_precision_recall_come_from_the_saved_files(
    degraded: tuple[Path, AnalysisReport],
) -> None:
    report = degraded[1]
    assert row_of(table(report, "rules"), "S100", "PLT-1")[2:] == [2, 20, 0, 0]
    prf = row_of(table(report, "precision_recall"), "V2T-A2", "both scales")
    assert prf[2:] == [4, 4, 0.5, 1.0, pytest.approx(2 / 3)]
    assert not [note for note in report.notes if "no re-score" in note]


def test_the_report_serializes_to_json_and_back(degraded: tuple[Path, AnalysisReport]) -> None:
    again = AnalysisReport.model_validate_json(degraded[1].model_dump_json())
    assert again == degraded[1]
