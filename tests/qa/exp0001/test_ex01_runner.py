"""The EX01 runner end to end on a toy corpus: arms, repeats, caches, cap, resume, replay."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from exp0001_toy import QIDS, fake_client, make_settings, run, write_inputs

from plantgraph.llm.models import CacheMiss
from plantgraph.qa.cascade.policy import load_policy
from plantgraph.qa.exp0001.ex01_models import CASCADE_ARM, Ex01RunConfig
from plantgraph.qa.exp0001.ex01_runner import CASCADE_POLICY_FILE, load_ex01_questions
from plantgraph.qa.exp0001.ex01_store import Ex01RunDir
from plantgraph.qa.harness.freeze import prompt_hashes


def _config(out_dir: Path) -> Ex01RunConfig:
    text = (out_dir / "run_config.json").read_text(encoding="utf-8")
    return Ex01RunConfig.model_validate_json(text)


def test_only_the_five_scored_questions_are_asked(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    assert [q.question_id for q in load_ex01_questions(settings.qa_path)] == QIDS


def test_a_full_run_writes_every_arm_repeat_and_the_derived_cascade(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    client, fake = fake_client()
    summary = run(settings, client)
    rows = Ex01RunDir(settings.out_dir).read_rows()
    assert summary.n_new_rows == 5 * 5 * 2
    assert summary.n_cascade_rows == 5 * 2
    assert len(rows) == 60
    assert {row.arm for row in rows} == {*settings.arms, CASCADE_ARM}
    assert all(row.answer_text and "HV4750.01" in row.answer_text for row in rows)
    assert len(fake.requests) > 0


def test_one_cache_file_per_repeat(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    run(settings, fake_client()[0])
    names = sorted(p.name for p in settings.out_dir.glob("cache_ex01_r*.sqlite"))
    assert names == ["cache_ex01_r1.sqlite", "cache_ex01_r2.sqlite"]


def test_the_run_config_records_the_commit_pins_prompts_and_question_hash(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    run(settings, fake_client()[0])
    config = _config(settings.out_dir)
    assert len(config.git_commit) == 40 and isinstance(config.git_dirty, bool)
    assert config.prompt_hashes == prompt_hashes()
    assert len(config.question_file_sha256) == 64 and config.qids == QIDS
    assert config.arms["ctx-gpt5mini"].pin.model_id == "openai/gpt-5-mini"


def test_the_toy_pins_are_the_sealed_pins_the_policy_names(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    run(settings, fake_client()[0])
    config = _config(settings.out_dir)
    tiers = {t.strategy: t.pin_sha256 for t in load_policy(CASCADE_POLICY_FILE).tiers}
    assert config.arms["cyp"].pin_sha256 == tiers["cypher_rag_plant"]
    assert config.arms["ag"].pin_sha256 == tiers["graph_agent_low_steps"]


def test_a_second_invocation_resumes_and_writes_nothing_new(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    client, fake = fake_client()
    run(settings, client)
    before = len(fake.requests)
    again = run(settings, client)
    assert again.n_new_rows == 0 and again.n_cascade_rows == 0
    assert len(fake.requests) == before


def test_a_resume_with_a_different_repeat_count_is_refused(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    run(settings, fake_client()[0])
    with pytest.raises(ValueError, match="repeats"):
        run(replace(settings, repeats=3), fake_client()[0])


def test_without_the_paid_flag_the_run_replays_the_cache_and_never_calls_out(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    client, fake = fake_client()
    run(settings, client)
    (settings.out_dir / "answers.jsonl").unlink()
    before = len(fake.requests)
    replay = run(replace(settings, allow_paid_calls=False))
    assert replay.n_new_rows == 50 and len(fake.requests) == before


def test_without_the_paid_flag_an_empty_cache_stops_at_the_first_miss(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, allow_paid_calls=False)
    with pytest.raises(CacheMiss):
        run(settings)


def test_the_spend_cap_stops_the_run_and_a_resume_continues(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, cap_usd=0.05)
    client, _ = fake_client(cost_usd=0.01)
    stopped = run(settings, client)
    assert stopped.stopped_by_spend_cap and 0 < stopped.n_new_rows < 50
    resumed = run(replace(settings, cap_usd=50.0), client)
    assert not resumed.stopped_by_spend_cap
    assert len(Ex01RunDir(settings.out_dir).read_rows()) == 60


def test_an_arm_the_registry_cannot_build_is_not_applicable_and_the_rest_run(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path)
    write_inputs(settings.inputs_dir, agent_params={"no_such_parameter": 1})
    summary = run(settings, fake_client()[0])
    rows = Ex01RunDir(settings.out_dir).read_rows()
    assert list(summary.not_applicable) == ["ag"]
    assert {row.arm for row in rows} == {"ctx-high", "ctx-low", "ctx-gpt5mini", "cyp"}
    assert summary.n_cascade_rows == 0  # a tier is missing, so no cascade is invented


def test_answers_are_free_text_and_carry_cost_and_context_size(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, arms=["ctx-high"], repeats=1)
    run(settings, fake_client()[0])
    first = (settings.out_dir / "answers.jsonl").read_text(encoding="utf-8").splitlines()[0]
    row = json.loads(first)
    assert row["outcome"] == "ANSWERED" and row["cost_usd"] == pytest.approx(0.001)
    assert row["context_chars"] > 0 and row["prompt_tokens"] > 0
