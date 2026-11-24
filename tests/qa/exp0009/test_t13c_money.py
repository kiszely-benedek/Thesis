"""T13c money rules: the audit split (B5), the complete G0f replay (B6), P1c's projection (F1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.qa.exp0009 import caps, launcher, ledger, stages
from plantgraph.qa.exp0009.launcher_commands import require_complete_replay


def _run(*argv: str) -> int:
    return launcher.main(list(argv))


# ---- B5: the main sample is sized with 2/3 of the audit cap when B is sealed -------------------


def test_the_main_sample_gets_two_thirds_of_the_audit_cap_with_b_and_all_of_it_without() -> None:
    assert ledger.main_sample_cap_usd(8.13, b_sealed=True) == pytest.approx(5.42)
    assert ledger.main_sample_cap_usd(8.13, b_sealed=False) == 8.13


def test_audit_cap_command_prints_the_total_the_left_and_the_main_sample_share(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def printed(*extra: str) -> float:
        assert _run("audit-cap", "--root", str(tmp_path), *extra) == 0
        return float(capsys.readouterr().out.strip())

    assert printed() == 8.13 and printed("--left") == 8.13
    assert printed("--for-main-sample", "yes") == pytest.approx(5.42)
    assert printed("--for-main-sample", "no") == 8.13


def test_both_judges_get_the_total_cap_and_the_shared_ledger_counts_each_dollar_once(
    tmp_path: Path,
) -> None:
    """Both judges get the total cap and share a ledger, so B's room is total - main's spend."""
    from plantgraph.qa.audit.budget import LedgerLine, SpendLedger

    total = ledger.AUDIT_CAP_USD
    shared = tmp_path / "ledger.jsonl"
    SpendLedger(shared, total).record(LedgerLine(stage="audit", item_key="m", paid_usd=5.0))
    b_judge = SpendLedger(shared, total)  # the B judge, given the same total cap
    assert b_judge.allows(3.0, "audit")  # 5.00 + 3.00 <= 8.13: not 8.13 - 2 x 5.00
    assert not b_judge.allows(3.2, "audit")


# ---- B6: G0f needs every row replayed ----------------------------------------------------------


@pytest.mark.parametrize("verdict", ["identical", "prefix_equal: 280 of 280 rows"])
def test_a_complete_replay_passes(verdict: str) -> None:
    require_complete_replay(verdict)


@pytest.mark.parametrize(
    "verdict", ["prefix_equal: 0 of 280 rows", "prefix_equal: 45 of 280 rows", "something else"]
)
def test_an_empty_or_short_prefix_is_not_a_complete_replay(verdict: str) -> None:
    with pytest.raises(ValueError, match="complete replay"):
        require_complete_replay(verdict)


def _answers(folder: Path, ids: list[str]) -> Path:
    folder.mkdir()
    rows = [{"question_id": q, "correct": True} for q in ids]
    (folder / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return folder


def test_replay_compare_command_rejects_a_zero_row_prefix_only_when_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _answers(tmp_path / "run", ["q1", "q2"])
    replay = _answers(tmp_path / "replay", [])
    base = ["replay-compare", "--replay-dir", str(replay), "--run-dir", str(run)]
    assert _run(*base, "--allow-prefix", "yes") == 0  # P1b, P1c and P1g keep prefixes (ADR-0062)
    assert "prefix_equal: 0 of 2 rows" in capsys.readouterr().out
    assert _run(*base, "--allow-prefix", "yes", "--require-complete", "yes") == 1
    assert "complete replay" in capsys.readouterr().err


# ---- F1: P1c's projection from P1b's measured costs --------------------------------------------


def test_the_projection_at_the_default_keys_is_the_estimate_of_section_19_9() -> None:
    projection = stages.project_p1c(None, b_sealed=True)
    assert projection.projected_usd == pytest.approx(14.06, abs=0.1)  # design §19.9, P1c
    assert projection.run_caps_usd["A2-ag-1000"] == caps.run_cap_usd(275, 0.001711)
    assert len(projection.run_caps_usd) == 8
    assert len(stages.project_p1c(None, b_sealed=False).run_caps_usd) == 4


def test_a_cost_above_the_ceiling_or_the_ledger_stops_before_f10() -> None:
    dear = {
        f"{arm}-{t}-{s}": 0.01 for arm in ("A2", "B") for t in ("cyp", "ag") for s in (100, 1000)
    }
    projection = stages.project_p1c(dear, b_sealed=True)
    assert stages.p1c_projection_problems(projection, runs_left_usd=26.87) != []
    cheap = stages.project_p1c(None, b_sealed=True)
    assert stages.p1c_projection_problems(cheap, runs_left_usd=26.87) == []
    short = stages.p1c_projection_problems(cheap, runs_left_usd=15.0)  # 15.00 - 2.50 GLM < 14.06
    assert len(short) == 1 and "GLM reserve" in short[0]


def test_project_command_writes_the_caps_for_part_b_and_raises_on_a_shortfall(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "b_sealed").write_text("yes\n", encoding="utf-8")
    measured = tmp_path / "measured.json"
    measured.write_text(json.dumps({"A2-cyp-100": 0.0008}), encoding="utf-8")
    out = tmp_path / "state" / "p1c_projection.json"
    argv = ["project-p1c", "--root", str(tmp_path), "--measured", str(measured), "--out", str(out)]
    assert _run(*argv) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["problems"] == [] and document["run_caps_usd"]["A2-cyp-100"] > 0
    assert _run(*argv, "--ceiling-usd", "1.0") == 1
    assert "exceeds the step ceiling" in capsys.readouterr().err
    assert json.loads(out.read_text(encoding="utf-8"))["problems"]  # recorded even when it stops
