"""Synthetic sealed roots for the T17 analysis tests (a helper module with one self-test).

`build_root` writes what END finds after P1c: a plan, `state/b_sealed`, question files, the two
tier runs of each arm of each plant, and the small descriptive inputs. The answers are canned so
every claim has a known value:

- every plant holds 20 scope R questions that count (4 families of 5), plus 2 LOOP_ACTUATED_VALVE
  and 2 held-out-wording questions that must stay out, 4 X isolation and 4 POSITION questions;
- the Cypher tier always answers and is accepted, so the cascade's answer is the Cypher tier's;
  the agent tier is right on everything;
- how many R questions A2 and B get right per scale, and how many X questions, is a `Recipe`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from cascade_toy import row
from cascade_v4_toy import USAGE, pin
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.v2.rules.registry import RuleReport, RuleRow
from plantgraph.benchmark.v2.tags import format_valve_tag
from plantgraph.qa.exp0009.analysis_x import BaselineRow
from plantgraph.qa.exp0009.plan import Exp0009Plan, PlantSpec22, Role, plant_id
from plantgraph.qa.exp0009.records import RescoreReport, RowScore
from plantgraph.qa.exp0009.scope_x_report import FamilyReport
from plantgraph.qa.harness.freeze import prompt_hashes, question_set_sha256
from plantgraph.qa.harness.question_set import questions_path
from plantgraph.qa.models import AnswerType, CorpusRecord, Question, QuestionFamily, RunConfig
from plantgraph.qa.questions.scope_x_models import QuestionFlags

F = QuestionFamily
R_FAMILIES = (F.FLOW_PATH, F.CONNECTED, F.CROSS_UNIT, F.LOOKUP_TYPE)
N_PER_R_FAMILY = 5  # so 20 R questions count per plant
CYPHER, AGENT = "cypher_rag_lines", "graph_agent_lines"
NETWORK_TAG = format_valve_tag("GTV", 9011, 1)  # a tag of a network unit (unit number 9000+)


@dataclass(frozen=True)
class QSpec:
    """One synthetic question and what each tier answers."""

    key: str
    family: QuestionFamily
    split: str
    cyp_ok: bool
    ag_ok: bool = True
    answer_type: AnswerType = AnswerType.BOOLEAN
    reference: str = "yes"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recipe:
    """How many questions each arm gets right (the first n of its list)."""

    a2_r: dict[int, int] = field(default_factory=lambda: {100: 20, 1000: 16})
    b_r: dict[int, int] = field(default_factory=lambda: {100: 20, 1000: 16})
    a2_x: int = 0  # of the 4 X isolation questions
    b_x: int = 4
    b_position: int = 2  # of the 4 POSITION questions
    plants_per_scale: int = 2


def r_specs(correct: int) -> list[QSpec]:
    """The 20 counted R questions (the first `correct` right) and the 4 that must stay out."""
    specs = []
    for f, family in enumerate(R_FAMILIES):
        for i in range(N_PER_R_FAMILY):
            n = f * N_PER_R_FAMILY + i
            tags = (NETWORK_TAG,) if n == 0 else ()
            specs.append(QSpec(f"{family.value}:{i}", family, "dev-old", n < correct, tags=tags))
    specs += [
        QSpec(f"LOOP_ACTUATED_VALVE:{i}", F.LOOP_ACTUATED_VALVE, "dev-old", False) for i in (0, 1)
    ]
    specs += [QSpec(f"WORDING:{i}", F.FLOW_PATH, "held-out-wording", False) for i in (0, 1)]
    return specs


def x_specs(isolation_correct: int, position_correct: int | None) -> list[QSpec]:
    """4 X isolation questions; 4 POSITION questions too when `position_correct` is given."""
    isolation = [
        QSpec(
            f"OPEN_VALVES_TO_ISOLATE:{i}", F.OPEN_VALVES_TO_ISOLATE, "x-dev", i < isolation_correct
        )
        for i in range(4)
    ]
    if position_correct is None:
        return isolation
    codes = ("NO", "NO", "NC", "NC")
    return isolation + [
        QSpec(
            f"POSITION_OF_VALVE:{i}", F.POSITION_OF_VALVE, "x-dev", i < position_correct,
            answer_type=AnswerType.POSITION, reference=codes[i],
        )
        for i in range(4)
    ]  # fmt: skip


def _question(corpus_id: str, spec: QSpec) -> Question:
    return Question(
        question_id=f"{corpus_id}:{spec.key}", corpus_id=corpus_id, family=spec.family,
        template_id=spec.family.value, template_version="1", text=f"text of {spec.key}",
        answer_type=spec.answer_type, answerable=True, reference=spec.reference,
        evidence_tags=list(spec.tags), generator_seed=1,
    )  # fmt: skip


def _rows(
    corpus_id: str, specs: list[QSpec], strategy: str, *, cypher: bool
) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        qid, ok = f"{corpus_id}:{spec.key}", spec.cyp_ok if cypher else spec.ag_ok
        extra = {"trace": {"retrieval": {"n_rows": 2, "truncated": False}}} if cypher else {}
        if cypher:
            extra["retrieval_usage"] = USAGE
        rows.append(row(qid, strategy, correct=ok, **extra))
    return rows


def write_run(
    runs_dir: Path, run_id: str, corpus_id: str, strategy: str, pin_file: str,
    rows: list[dict[str, Any]], questions_root: Path,
) -> None:  # fmt: skip
    """One tier run the way the harness writes it (config, corpus record, answers)."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    params = {"timeout_s": 30.0, "row_cap": 1000} if strategy == CYPHER else {}
    config = RunConfig(
        run_id=run_id, experiment="TOOLING", reported=False, corpora=[corpus_id],
        strategies={strategy: params}, answer_pin=pin(pin_file), prompt_hashes=prompt_hashes(),
        question_set_sha256=question_set_sha256([questions_path(questions_root, corpus_id)]),
        primer=True, git_commit="0" * 40, git_dirty=False, created_at=datetime(2026, 11, 24),
        repeats=1,
    )  # fmt: skip
    (run_dir / "run_config.json").write_text(config.model_dump_json(), encoding="utf-8")
    record = CorpusRecord(
        corpus_id=corpus_id, role="test", generator_config=GeneratorConfig(),
        split_config=SplitConfig(), n_sheets=1, n_store_nodes=1, n_connector_pairs_predicted=0,
        n_plant_nodes=1, n_plant_edges=0, source_graph_hash="g" * 64, stage_seconds={},
    )  # fmt: skip
    (run_dir / "corpora.json").write_text("[" + record.model_dump_json() + "]", encoding="utf-8")
    lines = "".join(json.dumps(r) + "\n" for r in rows)
    (run_dir / "answers.jsonl").write_bytes(lines.encode("utf-8"))


def write_questions(root: Path, corpus_id: str, specs: list[QSpec]) -> None:
    """`questions/<corpus id>/questions.jsonl` and `splits.json`."""
    folder = root / "questions" / corpus_id
    folder.mkdir(parents=True)
    lines = "".join(_question(corpus_id, s).model_dump_json() + "\n" for s in specs)
    (folder / "questions.jsonl").write_bytes(lines.encode("utf-8"))
    splits = {f"{corpus_id}:{s.key}": s.split for s in specs}
    (folder / "splits.json").write_text(json.dumps(splits), encoding="utf-8")


def write_arm(
    root: Path, runs_dir: Path, corpus_id: str, specs: list[QSpec], *, b: bool, prefix: str
) -> None:
    """The question files of one corpus and its two tier runs (`<prefix>-CYP-<id>`, `-AG-`)."""
    write_questions(root, corpus_id, specs)
    suffix = "_b" if b else ""
    for part, strategy, cypher, pin_file in (
        ("CYP", CYPHER + suffix, True, "pin_cypher_luna_low.json"),
        ("AG", AGENT + suffix, False, "pin_agent_luna_final_high.json"),
    ):
        rows = _rows(corpus_id, specs, strategy, cypher=cypher)
        run_id = f"{prefix}-{part}-{corpus_id}"
        write_run(runs_dir, run_id, corpus_id, strategy, pin_file, rows, root / "questions")


def _plan(plants_per_scale: int) -> Exp0009Plan:
    specs = [
        PlantSpec22(
            plant_id=plant_id(Role.SEALED, scale, k), role=Role.SEALED, scale=scale, seed=k,
            target_sheets=scale, n_units=1, predicted_sheets=scale, document_untagged=(True,),
        )
        for scale in (100, 1000)
        for k in range(1, plants_per_scale + 1)
    ]  # fmt: skip
    return Exp0009Plan(
        draw_seed=0, prior_sha256="0" * 64, majority_code={"tag": "NO", "descriptor": "NO"},
        plants=tuple(specs),
    )  # fmt: skip


def _write_inputs(root: Path, spec: PlantSpec22, recipe: Recipe) -> None:
    """Scope report, POSITION baselines, qpool flags, rules.json and END's re-scores."""
    a_id, b_id = spec.plant_id, spec.b_id
    family = FamilyReport(
        family=F.OPEN_VALVES_TO_ISOLATE, candidates=12, refused_no_descriptor=1,
        refused_empty_gold=1, kept=10, kept_with_untagged_gold=4, kept_discriminating=3,
        kept_named_by_descriptor=None, kept_position_mix={}, refusing_roles={},
    )  # fmt: skip
    report = {"scope_x": [family.model_dump(mode="json")]}
    (root / "questions" / a_id / "scope_report.json").write_text(json.dumps(report), "utf-8")
    baselines = [
        BaselineRow(
            question_id=f"{b_id}:POSITION_OF_VALVE:{i}", named_by="tag" if i < 3 else "descriptor",
            gold=("NO", "NO", "NC", "NC")[i], majority="NO", text_prior="NO" if i != 2 else "NC",
        )
        for i in range(4)
    ]  # fmt: skip
    lines = "".join(b.model_dump_json() + "\n" for b in baselines)
    (root / "questions" / b_id / "position_baselines.jsonl").write_text(lines, encoding="utf-8")
    flags = {
        f"{a_id}:OPEN_VALVES_TO_ISOLATE:{i}": QuestionFlags(
            holds_untagged=i < 2, differs_from_topological=i % 2 == 0
        ).model_dump(mode="json")
        for i in range(4)
    }  # fmt: skip
    flag_dir = root / "qpool" / a_id / "scope_x"
    flag_dir.mkdir(parents=True)
    (flag_dir / "flags.json").write_text(json.dumps(flags), encoding="utf-8")
    rules = RuleReport(
        generator_version="v2.2", rows=(RuleRow(rule_id="PLT-1", checked=10, violations=0),)
    )
    (root / "corpora" / a_id).mkdir(parents=True)
    (root / "corpora" / a_id / "rules.json").write_text(rules.model_dump_json(), encoding="utf-8")
    (root / "reports").mkdir(exist_ok=True)
    for corpus in (a_id, b_id):
        rescore = RescoreReport(
            rows=[
                RowScore(
                    question_id=f"{corpus}:q",
                    stored_correct=True,
                    correct=True,
                    precision=0.5,
                    recall=1.0,
                    f1=2 / 3,
                )
            ]  # fmt: skip
        )
        for tier in ("AG", "CYP"):  # END re-scores both tiers
            path = root / "reports" / f"rescore_{tier}_{corpus}.json"
            path.write_text(rescore.model_dump_json(), encoding="utf-8")


def build_root(root: Path, recipe: Recipe | None = None, *, b_sealed: bool = True) -> Path:
    """A sealed root with `recipe`'s accuracies; returns `root`."""
    recipe = recipe or Recipe()
    plan = _plan(recipe.plants_per_scale)
    (root / "prereg").mkdir(parents=True)
    (root / "prereg" / "plan.json").write_text(plan.model_dump_json(), encoding="utf-8")
    (root / "state").mkdir()
    (root / "state" / "b_sealed").write_text("yes\n" if b_sealed else "no\n", encoding="utf-8")
    runs_dir = root / "p1c" / "runs"
    for spec in plan.plants:
        a2 = r_specs(recipe.a2_r[spec.scale]) + x_specs(recipe.a2_x, None)
        b = r_specs(recipe.b_r[spec.scale]) + x_specs(recipe.b_x, recipe.b_position)
        write_arm(root, runs_dir, spec.plant_id, a2, b=False, prefix="S9")
        # B's question file always exists; its runs only when B ran sealed
        if b_sealed:
            write_arm(root, runs_dir, spec.b_id, b, b=True, prefix="S9")
        else:
            write_questions(root, spec.b_id, b)
        _write_inputs(root, spec, recipe)
    return root


def build_exp0008_root(root: Path, correct: dict[int, int]) -> Path:
    """A small EXP-0008 root: two sealed v2.1 plants per scale, `correct` of 20 questions right."""
    runs_dir = root / "m6a" / "runs"
    for scale in (100, 1000):
        for k in (1, 2):
            corpus = f"H{scale}g21p{k}"
            specs = r_specs(correct[scale])
            write_arm(root, runs_dir, corpus, specs, b=False, prefix="S7")
    return root


def test_the_builder_writes_both_arms_of_every_plant(tmp_path: Path) -> None:
    root = build_root(tmp_path / "root")
    assert len(list((root / "p1c" / "runs").iterdir())) == 4 * 2 * 2  # plants x arms x tiers
    assert (root / "questions" / "H100g22p1B" / "position_baselines.jsonl").is_file()
