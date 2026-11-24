"""The GLM comparison arm (design §20): pins, plants, questions, caps, estimate, records, wiring."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx2
import pytest
from exp0009_small import built_small, reply
from test_records import two_runs

from plantgraph.llm.models import ModelPin
from plantgraph.qa.exp0008.ledger import LedgerExhausted
from plantgraph.qa.exp0009 import caps, glm_arm, launcher, records
from plantgraph.qa.exp0009.plan import Exp0009Plan, Role
from plantgraph.qa.exp0009.smoke_plan import smoke_plan, smoke_prior_text
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.models import Question, RunConfig
from plantgraph.qa.questions.per_family import read_questions
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES

REPO = Path(__file__).resolve().parents[3]
EXP = REPO / "data" / "runs" / "exp0009"
INPUTS = EXP / "inputs"
PIN_FILES = {
    "cyp": ("pin_cypher_luna_low.json", "pin_cypher_glm_fireworks_low.json"),
    "ag": ("pin_agent_luna_final_high.json", "pin_agent_glm_fireworks_high.json"),
}


def _pin(name: str) -> ModelPin:
    return ModelPin.model_validate_json((INPUTS / name).read_text(encoding="utf-8"))


# ---- the pins ---------------------------------------------------------------------------------


@pytest.mark.parametrize("tier", ["cyp", "ag"])
def test_glm_pins_differ_from_a2_only_in_model_and_host(tier: str) -> None:
    luna, glm = (_pin(name).model_dump() for name in PIN_FILES[tier])
    changed = {key for key in luna if luna[key] != glm[key]}
    # temperature and seed follow the host: Fireworks lists no `seed`, Luna's host no `temperature`,
    # and every request carries require_parameters, so a parameter the host lacks would fail
    assert changed == {"model_id", "route_provider", "temperature", "seed"}
    assert glm["model_id"] == glm_arm.MODEL_ID and glm["route_provider"] == glm_arm.PROVIDER
    assert luna["extra"] == glm["extra"] and luna["max_output_tokens"] == glm["max_output_tokens"]


def test_effort_per_tier_is_a2s() -> None:
    assert _pin(PIN_FILES["cyp"][1]).extra["reasoning"] == {"effort": "low"}
    assert _pin(PIN_FILES["ag"][1]).extra["reasoning"] == {"effort": "high"}


@pytest.mark.skipif(not (REPO / "data/runs/cv1/pins_bakeoff").is_dir(), reason="no bake-off pins")
@pytest.mark.parametrize("tier,letter_file", [("cyp", "C_cypher.json"), ("ag", "C_answer.json")])
def test_glm_pins_are_the_bakeoff_config_c(tier: str, letter_file: str) -> None:
    bakeoff = ModelPin.model_validate_json(
        (REPO / "data/runs/cv1/pins_bakeoff" / letter_file).read_text(encoding="utf-8")
    )
    assert _pin(PIN_FILES[tier][1]) == bakeoff


def test_the_model_is_still_listed_in_the_cached_openrouter_lists() -> None:
    listing = REPO / "docs/private/30-experiments/openrouter-models-2026-10-10.json"
    if not listing.is_file():
        pytest.skip("no cached model list")
    ids = {m["id"] for m in json.loads(listing.read_text(encoding="utf-8"))["data"]}
    assert glm_arm.MODEL_ID in ids


def test_the_glm_pins_sit_in_the_hashed_inputs_folder() -> None:
    frozen = (EXP / "stages" / "p1b.sh").read_text(encoding="utf-8")
    assert "$SCRIPTS/inputs" in frozen and "$SCRIPTS/stages" in frozen  # E10 hashes both
    assert all((INPUTS / name).is_file() for _luna, name in PIN_FILES.values())


# ---- the plants -------------------------------------------------------------------------------


def _plan() -> Exp0009Plan:
    return smoke_plan(smoke_prior_text())


def test_the_arm_runs_the_first_sealed_plant_of_each_scale_in_plan_order() -> None:
    assert [p.plant_id for p in glm_arm.glm_plants(_plan())] == ["H100g22p1", "H1000g22p1"]
    plan = _plan()
    reordered = plan.model_copy(update={"plants": tuple(reversed(plan.plants))})
    first = [p.plant_id for p in glm_arm.glm_plants(reordered)]
    assert first == ["H100g22p5", "H1000g22p5"]  # plan order decides, not the plant number


def test_a_plan_without_sealed_plants_is_refused() -> None:
    plan = _plan()
    dev_only = plan.model_copy(update={"plants": tuple(plan.of_role(Role.DEV))})
    with pytest.raises(ValueError, match="sealed plant at scale 100"):
        glm_arm.glm_plants(dev_only)


def test_run_ids_cannot_be_mistaken_for_luna_runs() -> None:
    assert glm_arm.run_id("cyp", "H100g22p1") == "G9-GLM-CYP-H100g22p1"
    assert glm_arm.run_id("ag", "H1000g22p1") == "G9-GLM-AG-H1000g22p1"
    with pytest.raises(ValueError, match="tier"):
        glm_arm.run_id("ctx", "H100g22p1")
    p1g = (EXP / "stages" / "p1g.sh").read_text(encoding="utf-8")
    assert f"{glm_arm.RUN_PREFIX}-CYP-$PL_ID" in p1g and f"{glm_arm.RUN_PREFIX}-AG-$PL_ID" in p1g


# ---- the question files -----------------------------------------------------------------------


def _is_x(line: str) -> bool:
    x_families = {f.value for f in SCOPE_X_FAMILIES}
    return Question.model_validate_json(line).family.value in x_families


def test_glm_questions_are_the_a2_file_byte_for_byte_without_the_x_questions(
    tmp_path: Path,
) -> None:
    root = two_runs().root / "questions"
    spec, _corpora, _record = built_small()
    a2_file = root / spec.plant_id / "questions.jsonl"
    count = glm_arm.write_glm_questions(root / spec.plant_id, tmp_path / "out")
    a2_lines = a2_file.read_bytes().decode("utf-8").splitlines(keepends=True)
    expected = "".join(x for x in a2_lines if not _is_x(x))
    written = (tmp_path / "out" / "questions.jsonl").read_bytes().decode("utf-8")
    assert written == expected and count == len(expected.splitlines())
    assert any(_is_x(x) for x in a2_lines) and count < len(a2_lines)  # X was there, and is gone
    splits = json.loads((tmp_path / "out" / "splits.json").read_text(encoding="utf-8"))
    assert set(splits) == {
        Question.model_validate_json(x).question_id for x in expected.splitlines()
    }


def test_glm_questions_are_never_rewritten(tmp_path: Path) -> None:
    root = two_runs().root / "questions"
    spec, _corpora, _record = built_small()
    glm_arm.write_glm_questions(root / spec.plant_id, tmp_path)
    with pytest.raises(FileExistsError, match="questions.jsonl"):
        glm_arm.write_glm_questions(root / spec.plant_id, tmp_path)


# ---- money ------------------------------------------------------------------------------------


def _paid(path: Path, usd: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"response": {"from_cache": False, "cost_usd": usd}}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_glm_cost_key_is_a2s_at_the_top_of_the_ratio() -> None:
    a2 = caps.cost_per_question_usd("ag", 100, arm="A2")
    assert caps.cost_per_question_usd("ag", 100, arm="GLM") == round(a2 * 1.9, 6)
    # a measured Luna cost from P1b must not leak into the GLM key
    assert caps.cost_per_question_usd("ag", 100, arm="GLM", measured={"A2-ag-100": 9.0}) == round(
        a2 * 1.9, 6
    )


def test_the_stage_cap_is_two_fifty_and_cuts_a_runs_cap(tmp_path: Path) -> None:
    assert glm_arm.CAP_USD == 2.5 == caps.STEP_CEILING_USD["P1g"]
    step = tmp_path / "p1g"
    _paid(step / "runs" / "r1" / "calls.jsonl", 2.0)
    assert glm_arm.money_needed_usd(tmp_path, step) == pytest.approx(0.5)
    _paid(step / "runs" / "r2" / "calls.jsonl", 0.5)
    with pytest.raises(LedgerExhausted, match="cap of P1g"):
        glm_arm.money_needed_usd(tmp_path, step)


def test_the_stage_stops_when_the_runs_ledger_cannot_hold_the_cap(tmp_path: Path) -> None:
    assert glm_arm.money_needed_usd(tmp_path, tmp_path / "p1g") == 2.5
    _paid(tmp_path / "p1c" / "runs" / "x" / "calls.jsonl", 25.0)  # 26.87 - 25.00 = 1.87 left
    with pytest.raises(LedgerExhausted, match="runs ledger"):
        glm_arm.money_needed_usd(tmp_path, tmp_path / "p1g")


def test_glm_room_command_prints_the_money_or_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert launcher.main(["glm-room", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "2.5"
    _paid(tmp_path / "p1g" / "runs" / "r" / "calls.jsonl", 2.5)
    assert launcher.main(["glm-room", "--root", str(tmp_path)]) == 1
    assert "cap of P1g" in capsys.readouterr().err


def test_run_cap_command_cuts_a_glm_run_to_what_the_stage_has_left(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    questions = tmp_path / "q.jsonl"
    questions.write_text("x\n" * 235, encoding="utf-8")
    step = tmp_path / "p1g"
    argv = ["run-cap", "--questions", str(questions), "--tier", "ag", "--scale", "1000"]
    argv += ["--arm", "GLM", "--step", "P1g", "--root", str(tmp_path), "--step-dir", str(step)]
    assert launcher.main(argv) == 0
    full = float(capsys.readouterr().out)
    assert full == pytest.approx(235 * 0.001711 * 1.9 * 1.5, abs=1e-3)
    _paid(step / "runs" / "r" / "calls.jsonl", 2.2)
    assert launcher.main(argv) == 0
    assert float(capsys.readouterr().out) == pytest.approx(0.3)


def test_the_estimate_note_is_a2s_rate_times_the_glm_ratio(tmp_path: Path) -> None:
    loads = [glm_arm.PlantLoad("H100g22p1", 100, 235), glm_arm.PlantLoad("H1000g22p1", 1000, 235)]
    low, high = glm_arm.estimate_range_usd(loads)
    assert low == pytest.approx(235 * (0.00234 + 0.00244) * 1.2)
    assert high == pytest.approx(235 * (0.00234 + 0.00244) * 1.9)
    note = glm_arm.render_estimate(tmp_path, loads, balance="$37.11")
    for expected in ("H100g22p1 235 q", "x1.2-1.9", f"${low:.2f}-${high:.2f}", "hard cap $2.50"):
        assert expected in note
    assert "runs $0.0000" in note and "balance $37.11" in note


def test_glm_estimate_command_reads_the_arms_question_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prereg = tmp_path / "prereg"
    assert launcher.main(["draw", "--smoke", "--prereg", str(prereg)]) == 0
    for plant in ("H100g22p1", "H1000g22p1"):
        folder = tmp_path / "p1g" / "questions" / plant
        folder.mkdir(parents=True)
        (folder / "questions.jsonl").write_text("{}\n" * 7, encoding="utf-8")
    argv = ["glm-estimate", "--root", str(tmp_path), "--prereg", str(prereg)]
    assert launcher.main(argv) == 0
    assert "H1000g22p1 7 q" in capsys.readouterr().out


# ---- the measurement record on a fake-sender GLM run ------------------------------------------


def _glm_run(tmp_path: Path) -> tuple[Path, list[Question], list[dict[str, object]]]:
    """The A2 agent arm with the GLM agent pin, on the arm's question file, with a fake model."""
    spec, corpora, _record = built_small()
    root = two_runs().root
    qroot = tmp_path / "glm_questions"
    glm_arm.write_glm_questions(root / "questions" / spec.plant_id, qroot / spec.plant_id)
    questions = read_questions(qroot / spec.plant_id / "questions.jsonl")[0]
    seen: list[dict[str, object]] = []
    reference_of = {q.text: q.reference for q in questions}

    def handle(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body["messages"][0]["role"] == "system":
            return reply('{"done": true}')
        prompt = body["messages"][0]["content"]
        found = next(ref for text, ref in reference_of.items() if text in prompt)
        return reply(json.dumps({"answer": found, "not_present": False}))

    config = RunConfig.model_validate(
        {
            "run_id": "G9-GLM-AG-D100g22", "experiment": "TOOLING", "reported": False,
            "corpora": [spec.plant_id], "strategies": {"graph_agent_lines": {}},
            "answer_pin": _pin(PIN_FILES["ag"][1]).model_dump(), "prompt_hashes": prompt_hashes(),
            "question_set_sha256": question_set_sha256([questions_path(qroot, spec.plant_id)]),
            "primer": True, "git_commit": "0" * 40, "git_dirty": False,
            "created_at": "2026-11-24T00:00:00", "allow_paid_calls": True, "max_spend_usd": 100.0,
        }
    )  # fmt: skip
    run_harness(
        config=config, corpus_roles={spec.plant_id: "test"}, corpora_root=corpora,
        questions_root=qroot, runs_root=tmp_path / "runs", cache_path=tmp_path / "cache.sqlite",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handle)),
        progress=lambda _m: None,
    )  # fmt: skip
    return tmp_path / "runs" / "G9-GLM-AG-D100g22", questions, seen


def test_a_glm_run_keeps_the_same_records_as_an_a2_run(tmp_path: Path) -> None:
    run, questions, seen = _glm_run(tmp_path)
    assert records.check_run_records(run) == []
    records.require_complete_records(run)
    assert not any(_is_x(q.model_dump_json()) for q in questions)  # scope R only
    # the requests name the model and the one host, with no fallback (BAKEOFF-1's lesson)
    assert {b["model"] for b in seen} == {glm_arm.MODEL_ID}
    wanted = {"order": [glm_arm.PROVIDER], "allow_fallbacks": False}
    assert all(b["provider"] == wanted for b in seen)


def test_the_offline_rescore_reproduces_a_glm_run(tmp_path: Path) -> None:
    run, questions, _seen = _glm_run(tmp_path)
    spec, corpora, _record = built_small()
    inputs = records.inputs_from_corpus(
        spec.plant_id, corpora / spec.plant_id / "ingest.json", is_b=False
    )
    report = records.rescore(run, {q.question_id: q for q in questions}, inputs)
    assert report.rows and report.mismatches == []


# ---- the shell wiring -------------------------------------------------------------------------


def test_p1g_sits_after_p1c_and_before_p1d() -> None:
    text = (EXP / "run_all.sh").read_text(encoding="utf-8")
    stages_line = re.search(r'^STAGES="([^"]+)"', text, re.MULTILINE)
    assert stages_line is not None
    order = stages_line.group(1).split()
    assert order.index("P1c") + 1 == order.index("P1g") and order.index("P1g") + 1 == order.index(
        "P1d"
    )
    assert "stage_P1g()" in (EXP / "stages" / "p1g.sh").read_text(encoding="utf-8")


def test_the_arms_use_the_glm_pins_and_the_glm_cost_keys() -> None:
    lib = (EXP / "lib_runs.sh").read_text(encoding="utf-8")
    for name in ("pin_cypher_glm_fireworks_low.json", "pin_agent_glm_fireworks_high.json"):
        assert name in lib
    assert '--arm "$AR_COST_ARM"' in lib  # the cap and the reservation use GLM's keys, not A2's


def test_p1g_checks_money_before_the_first_run_and_replays_every_run() -> None:
    p1g = (EXP / "stages" / "p1g.sh").read_text(encoding="utf-8")
    assert p1g.index("p1g_preflight\n") < p1g.index("for_each_plant glm p1g_plant")
    assert "stop_run topup" in p1g and "glm-room" in p1g and "glm-estimate" in p1g
    assert p1g.count("replay_run") == 2 and p1g.count("paid_run") == 2


def test_prereg_a_fixes_the_plant_choice_rule() -> None:
    template = (EXP / "PREREG_A.template.md").read_text(encoding="utf-8")
    assert "first sealed plant of each scale in `plan.json` order" in template
    assert "z-ai/glm-5.3-flash" in template and "$2.50" in template
