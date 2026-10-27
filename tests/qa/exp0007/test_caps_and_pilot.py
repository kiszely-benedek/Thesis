"""Cap formula, the verified cap file, per-question costs and the pilot correction."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from plantgraph.qa.exp0007 import cap_plans, caps
from plantgraph.qa.exp0007.cli import main
from plantgraph.qa.exp0007.health import health_fault, outcome_counts
from plantgraph.qa.exp0007.pilot import (
    PILOT_FAMILIES,
    correction_of,
    filter_questions,
    head_questions,
    read_v1_baseline,
)
from plantgraph.qa.exp0007.run_costs import (
    QuestionCost,
    family_means,
    family_of,
    mean_usd_per_question,
    read_question_costs,
)


def _answer(
    qid: str, tokens: tuple[int, int], usd: float, retrieval: tuple[int, int, float] = (0, 0, 0.0)
) -> dict[str, Any]:
    return {
        "question_id": qid,
        "outcome": "ANSWERED",
        "prompt_tokens": tokens[0],
        "completion_tokens": tokens[1],
        "cost_usd": usd,
        "retrieval_usage": {
            "prompt_tokens": retrieval[0],
            "completion_tokens": retrieval[1],
            "cost_usd": retrieval[2],
        },
    }


def _run(root: Path, name: str, rows: list[dict[str, Any]]) -> Path:
    run = root / name
    run.mkdir(parents=True)
    (run / "answers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return run


def test_the_cap_rounds_up_to_five_cents_with_thirty_percent_headroom() -> None:
    assert caps.cap_usd(10, 0.001) == 0.05  # 0.013 -> one step
    assert caps.cap_usd(180, 0.000778) == 0.20  # 0.182 -> 0.20
    assert caps.cap_usd(100, 0.5 / 1.3 / 100) == 0.5  # exactly on a step stays there
    assert caps.cap_usd(1, 0.0) == 0.05  # never zero: a run must be able to start
    with pytest.raises(ValueError, match="n >= 1"):
        caps.cap_usd(0, 0.1)


def test_a_measured_floor_wins_over_the_scaled_v1_cost() -> None:
    plain = caps.make_entry("r", "ag", 100, 0.001, 2.0)
    floored = caps.make_entry("r", "ag", 100, 0.001, 2.0, floor_cost=0.005)
    assert plain.cost_per_question_usd == pytest.approx(0.002) and "measured" not in plain.basis
    assert floored.cost_per_question_usd == 0.005 and "measured v2" in floored.basis
    assert floored.cap_usd == caps.cap_usd(100, 0.005)


def test_the_cap_file_is_written_once_and_verified_by_hash(tmp_path: Path) -> None:
    file = caps.CapFile(stage="t", entries=[caps.make_entry("run-1", "cyp", 10, 0.001, 1.0)])
    path = tmp_path / "caps.json"
    digest = caps.write_cap_file(path, file)
    assert caps.load_verified(path, digest) == file
    assert caps.entry_for(file, "run-1").cap_usd == 0.05
    with pytest.raises(FileExistsError, match="never overwrite"):
        caps.write_cap_file(path, file)
    with pytest.raises(ValueError, match="to hash to"):
        caps.load_verified(path, "0" * 64)
    with pytest.raises(FileNotFoundError, match="cap file"):
        caps.load_verified(tmp_path / "missing.json", digest)
    with pytest.raises(KeyError, match="run-2"):
        caps.entry_for(file, "run-2")


def test_cap_of_through_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = caps.CapFile(stage="t", entries=[caps.make_entry("run-1", "cyp", 10, 0.001, 1.0)])
    digest = caps.write_cap_file(tmp_path / "caps.json", file)
    base = ["cap-of", "--cap-file", str(tmp_path / "caps.json"), "--run-id", "run-1"]
    with pytest.raises(SystemExit) as ok:
        main([*base, "--cap-sha256", digest])
    assert ok.value.code == 0 and capsys.readouterr().out.strip() == "0.05"
    with pytest.raises(SystemExit) as refused:
        main([*base, "--cap-sha256", "bad"])
    assert refused.value.code == 1 and "to hash to" in capsys.readouterr().err


def test_a_question_costs_every_call_behind_it(tmp_path: Path) -> None:
    run = _run(tmp_path, "r", [_answer("D:FLOW_PATH:a|b", (100, 10), 0.001, (400, 40, 0.004))])
    (cost,) = read_question_costs(run)
    assert (cost.family, cost.tokens, cost.usd) == ("FLOW_PATH", 550, pytest.approx(0.005))
    assert family_of("H1:LOOKUP_TYPE:T-1") == "LOOKUP_TYPE"
    with pytest.raises(ValueError, match="<corpus>:<FAMILY>"):
        family_of("nofamily")
    with pytest.raises(FileNotFoundError):
        read_question_costs(tmp_path / "none")
    assert mean_usd_per_question([cost]) == pytest.approx(0.005)


def _costs(per_family: dict[str, tuple[int, float]]) -> list[QuestionCost]:
    return [
        QuestionCost(question_id=f"D:{f}:x", family=f, tokens=t, usd=u)
        for f, (t, u) in per_family.items()
    ]


def test_the_correction_is_the_larger_of_the_token_and_dollar_ratios() -> None:
    v1 = _costs({f: (1000, 0.001) for f in PILOT_FAMILIES})
    v2 = _costs({f: (2500, 0.0015) for f in PILOT_FAMILIES})
    got = correction_of("ag", v2, v1)
    assert got.r_tokens == pytest.approx(2.5) and got.r_usd == pytest.approx(1.5)
    assert got.r == pytest.approx(2.5)
    cheaper = correction_of("ag", _costs({f: (500, 0.0005) for f in PILOT_FAMILIES}), v1)
    assert cheaper.r == 1.0  # a cap never shrinks against v1
    with pytest.raises(ValueError, match="every pilot family"):
        correction_of("ag", _costs({"CROSS_UNIT": (1, 1.0)}), v1)


def test_the_v1_baseline_must_reproduce_the_plans_token_sum(tmp_path: Path) -> None:
    rows = [_answer(f"D100:{f}:a", (100, 0), 0.001) for f in PILOT_FAMILIES]
    _run(tmp_path, "CYPL2-D100", rows)
    with pytest.raises(ValueError, match="20787 tokens"):
        read_v1_baseline(tmp_path, "cyp")
    assert family_means(read_question_costs(tmp_path / "CYPL2-D100"))["CROSS_UNIT"] == (
        100.0,
        0.001,
    )


def _questions_file(path: Path, families: list[str]) -> Path:
    path.write_text(
        "".join(
            json.dumps({"question_id": f"D:{f}:{i}", "family": f}) + "\n"
            for i, f in enumerate(families)
        )
    )
    return path


def test_the_pilot_keeps_ten_families_and_the_smoke_is_the_first_two(tmp_path: Path) -> None:
    source = _questions_file(tmp_path / "q.jsonl", [*PILOT_FAMILIES, "CONNECTED", "NO_PATH"])
    assert filter_questions(source, tmp_path / "pilot.jsonl", list(PILOT_FAMILIES)) == 10
    head_questions(tmp_path / "pilot.jsonl", tmp_path / "smoke" / "q.jsonl", 2)
    smoke = (tmp_path / "smoke" / "q.jsonl").read_text().splitlines()
    assert [json.loads(line)["family"] for line in smoke] == list(PILOT_FAMILIES[:2])
    short = _questions_file(tmp_path / "short.jsonl", list(PILOT_FAMILIES[:9]))
    with pytest.raises(ValueError, match="SHEETS_OF_TAG"):
        filter_questions(short, tmp_path / "x.jsonl", list(PILOT_FAMILIES))
    with pytest.raises(ValueError, match="at least 20"):
        head_questions(source, tmp_path / "y.jsonl", 20)


def test_the_pilot_caps_total_the_plans_ten_cents_and_dev_caps_scale(tmp_path: Path) -> None:
    assert cap_plans.pilot_caps().total_usd == pytest.approx(0.10)
    cv1 = tmp_path / "cv1"
    _run(cv1, "CYPL2-D100", [_answer("D100:A:1", (10, 0), 0.0004)])
    _run(cv1, "AGL3-D100", [_answer("D100:A:1", (10, 0), 0.0005)])
    questions = _questions_file(tmp_path / "dev.jsonl", ["A"] * 100)
    dev = cap_plans.dev_caps(
        cv1, questions, {"cyp": 2.0, "ag": 3.0}, {"cyp": "CYPL2-D100", "ag": "AGL3-D100"}
    )
    by_run = {e.run_id: e for e in dev.entries}
    assert by_run["Q7-CYP-D100g2"].cap_usd == caps.cap_usd(100, 0.0008)
    assert by_run["Q7-AG-D100g2"].cap_usd == caps.cap_usd(100, 0.0015)


def test_health_follows_the_sealed_rule(tmp_path: Path) -> None:
    ok = Counter({"ANSWERED": 90, "PROVIDER_ERROR": 10})
    assert health_fault(ok) is None  # exactly 10 % is allowed
    assert "PROVIDER_ERROR + PARSE_FAILURE" in (
        health_fault(Counter({"ANSWERED": 8, "PARSE_FAILURE": 2})) or ""
    )
    assert "RETRIEVAL_ERROR" in (health_fault(Counter({"ANSWERED": 3, "RETRIEVAL_ERROR": 7})) or "")
    assert health_fault(Counter()) is not None
    run = _run(tmp_path, "r", [{"question_id": "D:A:1", "outcome": "TIMED_OUT"}])
    assert outcome_counts(run) == Counter({"TIMED_OUT": 1})
