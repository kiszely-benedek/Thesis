"""Pools, the drop set, samples and the A2/B files (design §19.6, §19.12 5)."""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from exp0009_small import built_small

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0009 import question_files as qf
from plantgraph.qa.exp0009 import questions as qs
from plantgraph.qa.exp0009.position_baselines import KEY_FIELDS, FormPrior, fit_prior, position_rows
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.per_family import read_questions, sample_family
from plantgraph.qa.questions.scope_x_models import NamedBy

TINY = qs.Recipe("tiny", 1, 3, 3, 20261101, 2, 0, qs.SCOPE_X_DEV_FAMILIES)


@cache
def small_pool() -> qs.PlantPool:
    spec, root, _record = built_small()
    return qs.pool_step(
        load_corpus_artifacts(spec.plant_id, root / spec.plant_id / "ingest.json"), TINY
    )


def test_positions_of_the_plan_equal_the_generators() -> None:
    spec, _root, _record = built_small()
    config = spec.generator_config()
    assert dict(positions_of(plan_plant(config).unit_plans)) == dict(
        positions_of(generate_plant_v2(config).plan.unit_plans)
    )


def test_pool_step_finds_r_and_x_and_the_position_keys() -> None:
    pool = small_pool()
    assert pool.r_pool and pool.x_kept[QuestionFamily.POSITION_OF_VALVE]
    position_ids = {q.question_id for q in pool.x_kept[QuestionFamily.POSITION_OF_VALVE]}
    assert position_ids == set(pool.position_keys)


def test_pool_round_trips_through_disk(tmp_path: Path) -> None:
    pool = small_pool()
    qs.write_pool(tmp_path, pool)
    back = qs.read_pool(tmp_path)
    assert back.r_pool == pool.r_pool and back.x_kept == pool.x_kept
    assert back.position_keys == pool.position_keys and back.flags == pool.flags


def _files(tmp_path: Path) -> tuple[Path, list[Question], list[Question]]:
    pool = small_pool()
    drop = qf.DropSet(frozenset(qs.R_UNAVAILABLE), frozenset())
    priors = {form: _prior(form) for form in NamedBy}
    counts = qf.write_plant_files("D100g22", pool, drop, TINY, tmp_path, priors)
    assert counts["a2"] <= counts["b"]
    a = read_questions(tmp_path / "D100g22" / "questions.jsonl")[0]
    b = read_questions(tmp_path / "D100g22B" / "questions.jsonl")[0]
    return tmp_path, a, b


def _prior(form: NamedBy) -> FormPrior:
    """Fitted on the small plant's rows; an empty form (this plant prints no tags) gets "NO"."""
    rows = _rows(form)
    if rows:
        return fit_prior(form, rows)
    return FormPrior(form=form, key_fields=KEY_FIELDS[form], majority="NO", table={})


def _rows(form: NamedBy):  # type: ignore[no-untyped-def]
    spec, root, _r = built_small()
    plant = load_corpus_artifacts(spec.plant_id, root / spec.plant_id / "ingest.json").gold.plant
    positions = positions_of(plan_plant(spec.generator_config()).unit_plans)
    return position_rows(plant, positions, form)  # type: ignore[arg-type]


def test_a2_and_b_files_agree_on_shared_questions(tmp_path: Path) -> None:
    _root, a, b = _files(tmp_path)
    assert not any(q.answer_type in (AnswerType.POSITION, AnswerType.VALVE_SET) for q in a)
    strip = lambda q: (q.question_id.split(":", 1)[1], q.text, q.reference)  # noqa: E731
    b_by_id = {strip(q)[0]: q for q in b}
    for q in a:
        twin = b_by_id[q.question_id.split(":", 1)[1]]
        assert (q.text, q.reference) == (twin.text, twin.reference)
        assert q.corpus_id == "D100g22" and twin.corpus_id == "D100g22B"
        if twin.answer_type is AnswerType.VALVE_SET:
            assert q.answer_type is AnswerType.TAG_SET
        else:
            assert q.answer_type is twin.answer_type
    assert {q.question_id.split(":", 1)[1] for q in a} <= set(b_by_id)


def test_baselines_file_follows_the_fitted_priors(tmp_path: Path) -> None:
    root, _a, b = _files(tmp_path)
    lines = (root / "D100g22B" / qf.BASELINES_FILE).read_text(encoding="utf-8").splitlines()
    n_position = sum(q.family is QuestionFamily.POSITION_OF_VALVE for q in b)
    assert len(lines) == n_position > 0
    assert all('"text_prior"' in line and '"majority"' in line for line in lines)


def test_dropping_a_family_leaves_the_other_draws_unchanged() -> None:
    pool = small_pool()
    keep = qf.DropSet(frozenset(), frozenset())
    victim = next(iter({q.family for q in pool.r_pool}))
    drop = qf.DropSet(frozenset({victim}), frozenset())
    full, _s = qf.sample_r(pool, keep, TINY)
    cut, _s2 = qf.sample_r(pool, drop, TINY)
    assert [q for q in full if q.family is not victim] == cut
    family = next(f for f in pool.x_kept if pool.x_kept[f])
    assert qf.sample_x(pool, drop, TINY) == qf.sample_x(pool, keep, TINY)
    assert sample_family(pool.x_kept[family], 2, TINY.sample_seed)


def test_drop_set_names_families_short_on_any_plant() -> None:
    pool = small_pool()
    drop = qf.drop_set({"p": pool}, qs.SCOPE_X_DEV_FAMILIES)
    counts = qf.kept_counts(pool)
    assert all(counts[f] < qf.MIN_KEPT for f in drop.too_few)
    assert drop.pre_registered == qs.R_UNAVAILABLE
    assert Counter(q.family for q in pool.r_pool)


def test_relabel_changes_only_the_id() -> None:
    q = small_pool().r_pool[0]
    twin = qf.relabel_question(q, "D100g22", "D100g22B")
    assert twin.model_copy(update={"corpus_id": q.corpus_id, "question_id": q.question_id}) == q
    with pytest.raises(ValueError, match="expected corpus"):
        qf.relabel_question(q, "other", "otherB")


def test_pool_position_keys_are_the_baseline_module_keys() -> None:
    pool = small_pool()
    spec, root, _record = built_small()
    plant = load_corpus_artifacts(spec.plant_id, root / spec.plant_id / "ingest.json").gold.plant
    positions = positions_of(plan_plant(spec.generator_config()).unit_plans)
    known = {row.key for form in NamedBy for row in position_rows(plant, positions, form)}
    assert pool.position_keys and set(pool.position_keys.values()) <= known
