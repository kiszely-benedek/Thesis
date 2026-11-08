"""Gate G1, the E9 freeze rules, pre-registration part B and the stage state files (F15)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.qa.exp0008 import freeze, gates, prereg_b, smoke_evidence, state

NAMED = "a" * 40
LATER = "b" * 40


def _plant(plant: str, v2t: int, f1: int, weak: tuple[str, ...] = ()) -> gates.PlantEvidence:
    families = {f: (2, 10) if f in weak else (9, 10) for f in ("A", "B", "C")}
    return gates.PlantEvidence(
        plant=plant, n_questions=30, v2t_correct=v2t, f1_correct=f1, v2t_by_family=families
    )


def test_g1_passes_when_v2t_matches_or_beats_f1_on_both_plants() -> None:
    verdict = gates.g1_verdict([_plant("p100", 27, 27), _plant("p1000", 28, 24)])
    assert verdict.passed and not verdict.plants_where_v2t_below_f1


def test_g1_fails_when_v2t_is_below_f1_on_one_plant() -> None:
    verdict = gates.g1_verdict([_plant("p100", 27, 24), _plant("p1000", 20, 24)])
    assert not verdict.passed and verdict.plants_where_v2t_below_f1 == ["p1000"]
    assert "below F1 on ['p1000']" in gates.describe(verdict)


def test_g1_fails_for_a_family_below_half_on_both_plants_but_not_on_one() -> None:
    both = gates.g1_verdict([_plant("p100", 27, 24, ("B",)), _plant("p1000", 27, 24, ("B",))])
    one = gates.g1_verdict([_plant("p100", 27, 24, ("B",)), _plant("p1000", 27, 24)])
    assert not both.passed and both.families_weak_on_every_plant == ["B"]
    assert one.passed


def test_g1_needs_both_validation_plants() -> None:
    with pytest.raises(ValueError, match="both validation plants"):
        gates.g1_verdict([_plant("p100", 27, 24)])


def test_the_smoke_evidence_is_read_by_the_real_gate_and_can_be_made_to_fail(
    tmp_path: Path,
) -> None:
    for fail in (False, True):
        out = tmp_path / str(fail)
        smoke_evidence.write_g1_evidence(out, fail=fail)
        evidence = [
            gates.read_evidence(p, out / p / "tune_report.json", out / p / "dev_report.json")
            for p in ("VAL100g21", "VAL1000g21")
        ]
        assert gates.g1_verdict(evidence).passed is (not fail)


def test_part_a_must_name_the_code_commit() -> None:
    assert freeze.named_head(f"x\nFrozen code commit: `{NAMED}`\n") == NAMED
    with pytest.raises(freeze.FreezeRefused, match="Frozen code commit"):
        freeze.named_head("no commit here")


def test_a_dirty_tree_is_refused() -> None:
    freeze.check_clean("")
    with pytest.raises(freeze.FreezeRefused, match="clean tree under src/.*first: M src/x.py"):
        freeze.check_clean(" M src/x.py\n")


def test_head_must_be_the_named_commit_or_a_later_one_that_touches_only_the_prereg() -> None:
    freeze.check_head(NAMED, NAMED, [])
    freeze.check_head(
        LATER,
        NAMED,
        ["data/runs/exp0008/prereg/PREREG_A.md", "data/runs/exp0008/prereg/seeds.json"],
    )
    with pytest.raises(freeze.FreezeRefused, match="expected HEAD aaaaaaaaaa"):
        freeze.check_head(LATER, NAMED, ["src/plantgraph/qa/final_answer.py"])


def test_the_hash_file_is_written_once_in_sha256sum_format(tmp_path: Path) -> None:
    one, two = tmp_path / "one.txt", tmp_path / "two.txt"
    one.write_text("1", encoding="utf-8")
    two.write_text("2", encoding="utf-8")
    out = tmp_path / "E9.sha256"
    assert freeze.write_hash_file(out, [two, one, one]) == 2
    first = out.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith(freeze.sha256_of(one)) and first.endswith("one.txt")
    with pytest.raises(FileExistsError):
        freeze.write_hash_file(out, [one])


def test_the_audit_capacity_follows_the_pilots_measured_cost() -> None:
    # $10 less $0.50 spent, at 0.012 x 1.25 safety factor = 0.015 per call
    assert prereg_b.audit_capacity_calls(0.5, 0.012) == int(9.5 / 0.015)
    assert prereg_b.audit_capacity_calls(9.99, 0.012) == 0  # not even the worst-case call fits


def test_part_b_states_every_measured_number() -> None:
    verdict = gates.g1_verdict([_plant("p100", 27, 24), _plant("p1000", 28, 24)])
    part = prereg_b.PartB(
        code_commit=NAMED, g1=verdict, tau1=1.0, tau2=0.8888888888888888, pilot_rows=45,
        pilot_mean_call_usd=0.0123, pilot_spent_usd=0.55, g2_defects_found="23/25",
        g2_controls_correct="19/20", judge_template_sha256="t" * 8, judge_pin_sha256="p" * 8,
        step_caps_usd={"M5": 4.9}, e9_sha256_file_sha256="e" * 8, e9_files=7,
    )  # fmt: skip
    text = prereg_b.render_part_b(part)
    for expected in (
        NAMED,
        "**PASS**",
        "tau2 = 0.8888888888888888",
        "23/25",
        "0.01230",
        "| M5 | 4.90 |",
        "7 files",
    ):
        assert expected in text


def test_a_done_stage_is_skipped_only_while_its_outputs_hash_as_recorded(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    out.write_text("v1", encoding="utf-8")
    assert state.done_problem(tmp_path, "M0") == "no done marker"
    state.write_done(tmp_path, "M0", [out])
    assert state.done_problem(tmp_path, "M0") is None
    out.write_text("v2", encoding="utf-8")
    assert "changed since the stage finished" in str(state.done_problem(tmp_path, "M0"))
    out.unlink()
    assert "is missing" in str(state.done_problem(tmp_path, "M0"))


def test_a_stage_cannot_be_done_without_its_outputs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="expected stage M1 to have written"):
        state.write_done(tmp_path, "M1", [tmp_path / "nothing.txt"])


def test_stopped_names_the_stage_the_reason_and_the_resume_command(tmp_path: Path) -> None:
    state.write_stopped(tmp_path, "M5", "cap", "sh run_all.sh --from M5")
    assert (tmp_path / "STOPPED").read_text(encoding="utf-8") == (
        "stage: M5\nreason: cap\nresume: sh run_all.sh --from M5\n"
    )
    assert json.dumps({}) == "{}"
