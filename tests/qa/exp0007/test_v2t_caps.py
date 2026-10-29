"""R4 / R5 caps of V2T-A, priced from the validation runs' measured costs."""

from __future__ import annotations

from pathlib import Path

import pytest

from exp0007_fakes import (
    write_cost_run,
    write_e1_ctx_runs,
    write_prompt_sizes,
    write_questions,
    write_v7_runs,
)
from plantgraph.qa.exp0007.caps import entry_for, load_verified
from plantgraph.qa.exp0007.cli import main
from plantgraph.qa.exp0007.v2t_caps import (
    f1_baseline_total_usd,
    optional_total_usd,
    r4_v2t_caps,
    r5_v2t_caps,
    read_validation_costs,
)


@pytest.fixture
def v7_runs(tmp_path: Path) -> Path:
    return write_v7_runs(tmp_path / "v7")


@pytest.fixture
def ladder(tmp_path: Path) -> Path:
    for corpus in ("H1g2", "H3g2", "H10g2", "H30g2"):
        write_questions(tmp_path / "ladder", corpus, 92)
    return tmp_path / "ladder"


@pytest.fixture
def sealed(tmp_path: Path) -> tuple[Path, Path]:
    for corpus in ("H100g2", "H1000g2", "H100g2d0", "H100g2d50"):
        write_questions(tmp_path / "sealed", corpus, 560)
    write_questions(tmp_path / "c1", "H1000g2", 46)
    return tmp_path / "sealed", tmp_path / "c1"


def test_the_costs_are_the_validation_runs_means_over_all_calls(v7_runs: Path) -> None:
    costs = read_validation_costs(v7_runs)

    assert costs.small.v2t == pytest.approx({"cyp": 0.0007, "ag": 0.0014})
    assert costs.large.f1 == pytest.approx({"cyp": 0.0004, "ag": 0.0009})
    assert costs.worst("v2t", "cyp") == pytest.approx(0.0007)  # the dearer of the two plants


def test_a_missing_validation_run_is_named(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="V7-CYP-A-X100g2s212"):
        read_validation_costs(tmp_path)


def test_r4_prices_every_ladder_run_at_the_dearer_plant(
    v7_runs: Path, ladder: Path, tmp_path: Path
) -> None:
    caps = r4_v2t_caps(
        read_validation_costs(v7_runs),
        ladder,
        write_prompt_sizes(tmp_path / "p.json"),
        write_e1_ctx_runs(tmp_path / "e1"),
    )

    ids = [e.run_id for e in caps.entries]
    assert ids[:2] == ["E7-CYP-H1g2-SMOKE", "E7-CYP-H1g2"]  # the smoke runs on H1g2 only
    v2t_ids = [i for i in ids if not i.startswith("E7-CTXH-")]
    assert sum("SMOKE" in i for i in v2t_ids) == 2 and len(v2t_ids) == 10
    agent = next(e for e in caps.entries if e.run_id == "E7-AG-H30g2")
    assert (agent.n_questions, agent.cost_per_question_usd) == (92, pytest.approx(0.0014))
    assert agent.cap_usd == 0.2  # 1.3 x 92 x 0.0014 = 0.167 -> next 5 cents
    smoke = next(e for e in caps.entries if e.run_id == "E7-AG-H1g2-SMOKE")
    assert (smoke.n_questions, smoke.cap_usd) == (2, 0.02)


def test_r5_prices_the_1000_sheet_corpus_at_its_own_plant(
    v7_runs: Path, sealed: tuple[Path, Path]
) -> None:
    caps = r5_v2t_caps(read_validation_costs(v7_runs), *sealed)

    big = entry_for(caps, "S7-AG-H1000g2")
    small = entry_for(caps, "S7-AG-H100g2d50")
    assert big.cost_per_question_usd == pytest.approx(0.0013)  # X1000g2s213's agent cost
    assert small.cost_per_question_usd == pytest.approx(0.0014)  # X100g2s212's
    assert big.cap_usd == 0.95  # 1.3 x 560 x 0.0013 = 0.946, up to the next 5 cents
    c1 = entry_for(caps, "S7-AG-H1000g2-C1")
    assert (c1.n_questions, c1.cap_usd) == (46, 0.1)


def test_r5_has_the_f1_baseline_on_two_corpora_in_the_same_file(
    v7_runs: Path, sealed: tuple[Path, Path]
) -> None:
    caps = r5_v2t_caps(read_validation_costs(v7_runs), *sealed)

    baseline = [e.run_id for e in caps.entries if e.run_id.startswith("S7F1-")]
    assert baseline == [
        "S7F1-CYP-H100g2",
        "S7F1-AG-H100g2",
        "S7F1-CYP-H1000g2",
        "S7F1-AG-H1000g2",
    ]
    assert entry_for(caps, "S7F1-AG-H1000g2").cost_per_question_usd == pytest.approx(0.0009)
    assert f1_baseline_total_usd(caps) == pytest.approx(
        sum(entry_for(caps, i).cap_usd for i in baseline)
    )


def test_r4_measured_cost_is_a_floor_for_r5(
    v7_runs: Path, sealed: tuple[Path, Path], tmp_path: Path
) -> None:
    r4_runs = tmp_path / "r4"
    write_cost_run(r4_runs, "E7-AG-H30g2", 0.002)  # dearer than both validation plants
    write_cost_run(r4_runs, "E7-CYP-H30g2", 0.0001)  # cheaper: no effect

    caps = r5_v2t_caps(read_validation_costs(v7_runs), *sealed, r4_runs=r4_runs)

    assert entry_for(caps, "S7-AG-H1000g2").cost_per_question_usd == pytest.approx(0.002)
    assert "raised to R4's measured" in entry_for(caps, "S7-AG-H1000g2").basis
    assert entry_for(caps, "S7-CYP-H1000g2").cost_per_question_usd == pytest.approx(0.0006)
    assert entry_for(caps, "S7F1-AG-H1000g2").cost_per_question_usd == pytest.approx(0.0009)


def test_the_command_writes_a_cap_file_whose_hash_it_prints(
    v7_runs: Path, ladder: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "caps_r4.json"

    with pytest.raises(SystemExit) as stop:
        main(
            ["make-v2t-caps", "--stage", "r4", "--v7-runs", str(v7_runs),
             "--ladder-questions", str(ladder), "--out", str(out),
             "--prompt-size", str(write_prompt_sizes(tmp_path / "p.json")),
             "--e1-runs", str(write_e1_ctx_runs(tmp_path / "e1"))]
        )  # fmt: skip

    assert stop.value.code == 0
    printed = capsys.readouterr().out
    digest = printed.split("sha256 ")[1].split()[0]
    assert entry_for(load_verified(out, digest), "E7-CYP-H10g2").n_questions == 92
    assert (
        "optional F1 baseline $0.00" in printed and "optional ContextRAG small ladder $" in printed
    )


def test_the_command_refuses_a_stage_without_its_questions(v7_runs: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        main(["make-v2t-caps", "--stage", "r5", "--v7-runs", str(v7_runs),
              "--out", str(tmp_path / "x.json")])  # fmt: skip

    assert stop.value.code == 1


def test_setting_a_deadline_is_printed_and_the_params_must_carry_its_timeout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    params = tmp_path / "p.json"
    params.write_text('{"cypher_rag_lines": {"timeout_s": 30, "row_cap": 1000}}')
    with pytest.raises(SystemExit) as ok:
        main(["setting-deadline", "--setting", "A", "--cypher-params", str(params)])
    assert ok.value.code == 0 and capsys.readouterr().out.strip() == "120"

    params.write_text('{"cypher_rag_lines": {"timeout_s": 120, "row_cap": 1000}}')
    with pytest.raises(SystemExit) as bad:
        main(["setting-deadline", "--setting", "A", "--cypher-params", str(params)])
    assert bad.value.code == 1
    assert "expected timeout_s 30" in capsys.readouterr().err


def test_the_contextrag_arm_is_priced_from_the_prompt_size_and_the_billed_prices(
    v7_runs: Path, ladder: Path, tmp_path: Path
) -> None:
    caps = r4_v2t_caps(
        read_validation_costs(v7_runs),
        ladder,
        write_prompt_sizes(tmp_path / "p.json"),
        write_e1_ctx_runs(tmp_path / "e1"),
    )

    ctx = [e.run_id for e in caps.entries if e.run_id.startswith("E7-CTXH-")]
    assert ctx == ["E7-CTXH-H1g2-SMOKE", "E7-CTXH-H1g2", "E7-CTXH-H3g2", "E7-CTXH-H10g2"]
    h1 = entry_for(caps, "E7-CTXH-H1g2")
    # 20,000 x $0.125/M + 2 x 200 completion tokens x $0.5/M
    assert h1.cost_per_question_usd == pytest.approx(0.0025 + 0.0002)
    assert (h1.n_questions, h1.cap_usd) == (92, 0.35)  # 1.3 x 92 x 0.0027 = 0.323
    smoke = entry_for(caps, "E7-CTXH-H1g2-SMOKE")
    assert (smoke.n_questions, smoke.cap_usd) == (2, 0.05)
    h10 = entry_for(caps, "E7-CTXH-H10g2")
    assert h10.cost_per_question_usd == pytest.approx(0.02 + 0.0012)
    assert h10.cap_usd == 2.55  # 1.3 x 92 x 0.0212 = 2.5355
    assert optional_total_usd(caps, "E7-CTXH-") == pytest.approx(
        sum(entry_for(caps, i).cap_usd for i in ctx)
    )


def test_a_contextrag_prompt_above_the_price_step_is_refused(
    v7_runs: Path, ladder: Path, tmp_path: Path
) -> None:
    sizes = write_prompt_sizes(
        tmp_path / "p.json", {"H1g2": 20_000, "H3g2": 40_000, "H10g2": 300_000}
    )

    with pytest.raises(ValueError, match="below the price step"):
        r4_v2t_caps(
            read_validation_costs(v7_runs), ladder, sizes, write_e1_ctx_runs(tmp_path / "e1")
        )


def test_a_missing_prompt_size_is_named(v7_runs: Path, ladder: Path, tmp_path: Path) -> None:
    sizes = write_prompt_sizes(tmp_path / "p.json", {"H1g2": 20_000})

    with pytest.raises(ValueError, match="prompt size for H3g2"):
        r4_v2t_caps(
            read_validation_costs(v7_runs), ladder, sizes, write_e1_ctx_runs(tmp_path / "e1")
        )
