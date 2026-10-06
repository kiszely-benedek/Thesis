"""The cascade policy engine: decisions, scoring, references, bootstrap, policy files, gold ban."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import plantgraph.qa.cascade as cascade_package
from cascade_toy import (
    CORPUS,
    CYPHER,
    NEED,
    ToyRun,
    cypher_rows,
    need_rows,
    policy,
    write_questions,
    write_run,
)
from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.evaluate import compare, evaluate_policy, first_tier_acceptance
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.models import CascadePolicy, Decision
from plantgraph.qa.cascade.policy import POLICIES_DIR, decide_all, load_policies
from plantgraph.qa.cascade.references import evaluate_always, evaluate_oracle, random_escalation
from plantgraph.qa.cascade.stats import median, paired_bootstrap, percentile
from plantgraph.qa.need.labels import NeedLabel

Rows = list[dict[str, Any]]


def _with_correct(rows: Rows, correct: dict[str, bool]) -> Rows:
    return [{**r, "correct": correct.get(r["question_id"], r["correct"])} for r in rows]


def _join(
    tmp_path: Path,
    cypher: Rows | None = None,
    need: Rows | None = None,
    the_policy: CascadePolicy | None = None,
) -> JoinedCorpus:
    questions_root = write_questions(tmp_path / "questions")
    runs_root = tmp_path / "runs"
    cypher_run = ToyRun("c", CYPHER, "low", cypher or cypher_rows())
    need_run = ToyRun("n", NEED, "default", need or need_rows())
    sources = {
        "cypher-low": TierSource(write_run(runs_root, questions_root, cypher_run)),
        "need-default": TierSource(write_run(runs_root, questions_root, need_run)),
    }
    return join_corpus(the_policy or policy(), sources, CORPUS, questions_root)


def _decisions(joined: JoinedCorpus) -> list[Decision]:
    return decide_all(joined.policy, joined.question_ids, joined.need_labels, joined.signals)


def _by_id(joined: JoinedCorpus) -> dict[str, Decision]:
    return {d.question_id: d for d in _decisions(joined)}


def _need_rows_with_q2_runaway() -> Rows:
    return [
        {**r, "outcome": "PARSE_FAILURE", "final_answer": None}
        if r["question_id"] == "T1:q2"
        else r
        for r in need_rows()
    ]


def test_cascade_walks_tiers_and_sums_cost_and_latency(tmp_path: Path) -> None:
    by_id = _by_id(_join(tmp_path))

    # q1: tier 1 accepted (cost 0.001 final call + 0.002 query-writing call)
    assert by_id["T1:q1"].tiers_tried == ("cypher-low",)
    assert by_id["T1:q1"].answered_by == "cypher-low"
    assert by_id["T1:q1"].cost_usd == pytest.approx(0.003)
    # q2: empty result -> escalated, tier 2 answers; costs and latencies add up
    assert by_id["T1:q2"].tiers_tried == ("cypher-low", "need-default")
    assert by_id["T1:q2"].answered_by == "need-default"
    assert by_id["T1:q2"].cost_usd == pytest.approx(0.004)
    assert by_id["T1:q2"].latency_s == pytest.approx(2.0)
    # q3: retrieval error, then a parse failure -> the question fails
    assert by_id["T1:q3"].answered_by is None
    # q4: an abstaining tier-1 answer is escalated, and tier 2 answers
    assert by_id["T1:q4"].answered_by == "need-default"


def test_fallback_returns_the_first_tier_answer_unless_switched_off(tmp_path: Path) -> None:
    need = _need_rows_with_q2_runaway()
    no_fallback_policy = policy(fallback_to_first_answer=False)

    with_fallback = _by_id(_join(tmp_path / "a", need=need))
    without = _by_id(_join(tmp_path / "b", need=need, the_policy=no_fallback_policy))

    # q2: tier 1 answered (empty result) and tier 2 ran away -> tier 1 is the fallback
    assert with_fallback["T1:q2"].answered_by == "cypher-low"
    assert without["T1:q2"].answered_by is None
    # q3: tier 1 was a retrieval error, so there is nothing to fall back to
    assert with_fallback["T1:q3"].answered_by is None


def test_labels_can_start_a_question_later_or_stop_it_earlier(tmp_path: Path) -> None:
    routed = policy(
        start_tier_by_label={NeedLabel.ITEM: 1},  # ITEM: straight to tier 2
        last_tier_by_label={NeedLabel.PATH: 0, NeedLabel.UPSTREAM_ALL: 0},  # never escalate
    )

    by_id = _by_id(_join(tmp_path, the_policy=routed))

    assert by_id["T1:q2"].tiers_tried == ("need-default",)  # tier 1 skipped: no tier-1 cost
    assert by_id["T1:q2"].cost_usd == pytest.approx(0.001)
    assert by_id["T1:q3"].tiers_tried == ("cypher-low",)  # stopped at tier 1 (a retrieval error)
    assert by_id["T1:q3"].answered_by is None


def test_a_missing_tier_row_is_refused_not_filled(tmp_path: Path) -> None:
    joined = _join(tmp_path, need=need_rows()[:1])  # tier 2 has q1 only

    with pytest.raises(ValueError, match="row for question 'T1:q2' in tier 'need-default'"):
        _decisions(joined)


def test_evaluation_reads_correct_from_the_answering_tier(tmp_path: Path) -> None:
    cypher = _with_correct(cypher_rows(), {"T1:q1": True, "T1:q2": False, "T1:q4": False})
    need = _with_correct(need_rows(), {"T1:q2": True, "T1:q4": False})

    evaluation = evaluate_policy(_join(tmp_path, cypher=cypher, need=need))

    summary = evaluation.summary
    assert [s.correct for s in evaluation.scored] == [True, True, False, False]
    assert (summary.n_correct, summary.n_questions) == (2, 4)
    assert summary.total_cost_usd == pytest.approx(0.003 + 0.004 + 0.004 + 0.004)
    assert summary.tier_shares == {"cypher-low": 0.25, "need-default": 0.5, "none": 0.25}
    assert summary.tier_calls == {"cypher-low": 4, "need-default": 3}


def test_first_tier_acceptance_precision_and_recall(tmp_path: Path) -> None:
    cypher = _with_correct(cypher_rows(), {"T1:q1": False, "T1:q2": True, "T1:q4": True})
    joined = _join(tmp_path, cypher=cypher)

    acceptance = first_tier_acceptance(joined, joined.policy)

    assert (acceptance.n_accepted, acceptance.n_accepted_correct) == (1, 0)  # only q1 accepted
    assert acceptance.n_first_tier_correct == 3  # q2, q4 and q3 (toy rows default to correct)
    assert acceptance.precision == 0.0 and acceptance.recall == 0.0


def test_always_reference_uses_only_one_tier(tmp_path: Path) -> None:
    joined = _join(tmp_path, need=_need_rows_with_q2_runaway())

    always_need = evaluate_always(joined, joined.policy.tiers[1])
    always_cypher = evaluate_always(joined, joined.policy.tiers[0])

    assert always_need.summary.policy == "always-need-default"
    assert always_need.summary.tier_calls == {"need-default": 4}
    # always-cypher keeps even an empty answer, but a retrieval error still fails
    final = [s.decision.answered_by for s in always_cypher.scored]
    assert final == ["cypher-low", "cypher-low", None, "cypher-low"]


def test_oracle_escalates_exactly_the_wrong_first_tier_answers(tmp_path: Path) -> None:
    cypher = _with_correct(
        cypher_rows(), {"T1:q1": True, "T1:q2": False, "T1:q3": False, "T1:q4": True}
    )

    oracle = evaluate_oracle(_join(tmp_path, cypher=cypher))

    tried = {s.decision.question_id: s.decision.tiers_tried for s in oracle.scored}
    assert tried["T1:q1"] == ("cypher-low",)  # correct -> kept
    assert tried["T1:q4"] == ("cypher-low",)  # correct although the policy would escalate it
    assert tried["T1:q2"] == ("cypher-low", "need-default")
    assert tried["T1:q3"] == ("cypher-low", "need-default")
    assert oracle.summary.policy == "oracle(toy)"


def test_random_reference_is_reproducible_and_escalates_the_policys_count(tmp_path: Path) -> None:
    joined = _join(tmp_path)

    first = random_escalation(joined, n_draws=50, seed=7)
    again = random_escalation(joined, n_draws=50, seed=7)
    other = random_escalation(joined, n_draws=50, seed=8)

    assert first == again
    assert first.n_escalated == 3  # the policy itself escalates q2, q3 and q4
    assert first.expected_latency_s != other.expected_latency_s
    assert first.correct_low <= first.correct_mean <= first.correct_high


def test_random_reference_refuses_a_label_policy(tmp_path: Path) -> None:
    joined = _join(tmp_path, the_policy=policy(start_tier_by_label={NeedLabel.ITEM: 1}))

    with pytest.raises(ValueError, match="label-free"):
        random_escalation(joined)


def test_flipping_every_correct_leaves_every_decision_unchanged(tmp_path: Path) -> None:
    """The policy must be blind to gold: decisions are byte-identical for opposite gold."""
    routed = policy(start_tier_by_label={NeedLabel.ITEM: 1}, last_tier_by_label={NeedLabel.PATH: 0})
    for index, the_policy in enumerate([policy(), routed]):
        flipped_cypher = [{**r, "correct": not r["correct"]} for r in cypher_rows()]
        flipped_need = [{**r, "correct": not r["correct"]} for r in need_rows()]
        original = _join(tmp_path / f"o{index}", the_policy=the_policy)
        flipped = _join(tmp_path / f"f{index}", flipped_cypher, flipped_need, the_policy=the_policy)

        before = [d.model_dump_json() for d in _decisions(original)]
        after = [d.model_dump_json() for d in _decisions(flipped)]

        assert before == after
        # sanity: the flip does change the score, so the test would notice a gold dependency
        assert evaluate_policy(original).summary.n_correct != (
            evaluate_policy(flipped).summary.n_correct
        )


GOLD_MODULES = ("plantgraph.qa.scoring", "plantgraph.qa.questions", "plantgraph.qa.harness.gold")


def _imported_modules(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("module", ["policy", "signals", "accept", "models", "stats"])
def test_policy_side_modules_never_import_gold_code(module: str) -> None:
    path = Path(cascade_package.__file__).parent / f"{module}.py"

    banned = {m for m in _imported_modules(path) if m.startswith(GOLD_MODULES)}

    assert not banned, f"{module}.py imports gold-side code: {sorted(banned)}"


def test_importing_the_policy_does_not_load_gold_code() -> None:
    code = (
        "import sys, plantgraph.qa.cascade.policy, plantgraph.qa.cascade.signals\n"
        f"bad = [m for m in sys.modules if m.startswith({GOLD_MODULES!r})]\n"
        "assert not bad, bad\n"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_percentiles_and_median() -> None:
    assert median([4.0, 1.0, 3.0, 2.0]) == 2.5
    assert median([3.0, 1.0, 2.0]) == 2.0
    assert percentile([float(i) for i in range(1, 101)], 90) == 90.0  # nearest rank
    with pytest.raises(ValueError, match="at least one"):
        percentile([], 50)


def test_paired_bootstrap_is_seeded_and_pairs_questions() -> None:
    a = [1.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    b = [0.0, 1.0, 0.0, 0.0, 1.0, 0.0]

    first = paired_bootstrap(a, b, n_resamples=500, seed=3)

    assert first == paired_bootstrap(a, b, n_resamples=500, seed=3)
    assert first.mean == pytest.approx(1 / 3)
    assert first.ci_low <= first.mean <= first.ci_high
    constant = paired_bootstrap([2.0, 3.0, 4.0], [1.0, 2.0, 3.0], n_resamples=200)
    assert (constant.ci_low, constant.ci_high) == (1.0, 1.0)  # a constant gap has no spread
    with pytest.raises(ValueError, match="equal-length"):
        paired_bootstrap([1.0], [1.0, 2.0])


def test_compare_gives_policy_minus_reference(tmp_path: Path) -> None:
    joined = _join(tmp_path)

    result = compare(
        evaluate_policy(joined).series(), evaluate_always(joined, joined.policy.tiers[0]).series()
    )

    assert result.cost_usd.mean > 0  # escalating costs more than tier 1 alone


# ---- the shipped policy files ---------------------------------------------------------------

GLM = "z-ai/glm-5.3-flash"
LOW = {"reasoning": {"effort": "low"}}


def _pin_hash(model: str, max_tokens: int, extra: dict[str, Any]) -> str:
    pin = ModelPin(
        backend="openrouter",
        model_id=model,
        temperature=0.0,
        seed=0,
        max_output_tokens=max_tokens,
        extra=extra,
    )
    return pin.pin_hash()


def test_policy_files_load_with_the_pins_the_note_names() -> None:
    policies = load_policies()
    expected_pins = {
        "cypher-low": _pin_hash(GLM, 16384, LOW),
        "need-default": _pin_hash(GLM, 16384, {}),
        "need-mimo": _pin_hash("xiaomi/mimo-v2.6-pro", 16384, {}),
        "need-low": _pin_hash(GLM, 16384, LOW),
        "need-default-64k": _pin_hash(GLM, 65536, {}),
    }

    assert set(policies) == {
        "always_n", "always_c", "cascade_v1", "cascade_v1_iso", "label_router_dev",
        "cascade_v1_t3_mimo", "cascade_v1_t3_glmlow", "cascade_v1_t3_glm64k",
        "n_first_v1_t3_mimo", "n_first_v1_t3_glmlow", "n_first_v1_t3_glm64k",
    }  # fmt: skip
    for loaded in policies.values():
        for tier in loaded.tiers:
            assert tier.pin_sha256 == expected_pins[tier.name]
    tier_names = [t.name for t in policies["cascade_v1_t3_glm64k"].tiers]
    assert tier_names == ["cypher-low", "need-default", "need-default-64k"]
    assert policies["cascade_v1_iso"].start_tier_by_label == {NeedLabel.UPSTREAM_TO_FIRST_VALVE: 1}
    assert not policies["cascade_v1"].start_tier_by_label
    assert (POLICIES_DIR / "cascade_v1.json").is_file()


# ---- optional: the design note's numbers on the real dev runs -------------------------------

RUNS = Path("data/runs/cv1")
HAVE_DATA = (RUNS / "runs" / "DEV10-D1000" / "answers.jsonl").is_file() and (
    RUNS / "runs" / "CYP-D1000-low" / "answers.jsonl"
).is_file()


def _real_join(name: str, corpus: str) -> JoinedCorpus:
    cypher = {"D100": "CYP-D100-low", "D1000": "CYP-D1000-low"}[corpus]
    sources = {
        "cypher-low": TierSource(RUNS / "runs" / cypher),
        "need-default": TierSource(RUNS / "runs" / f"DEV10-{corpus}"),
    }
    return join_corpus(load_policies()[name], sources, corpus, RUNS / "questions")


@pytest.mark.skipif(not HAVE_DATA, reason="needs the git-ignored data/runs/cv1 dev runs")
@pytest.mark.parametrize(
    ("name", "corpus", "correct", "cost"),
    [
        ("always_n", "D100", 157, 0.4692),
        ("always_c", "D100", 141, 0.0420),
        ("cascade_v1", "D100", 167, 0.2425),
        ("cascade_v1_iso", "D100", 170, 0.2663),
        ("label_router_dev", "D100", 167, 0.1458),
        ("cascade_v1", "D1000", 161, 0.3757),
    ],
)
def test_design_note_numbers_reproduce_on_the_dev_runs(
    name: str, corpus: str, correct: int, cost: float
) -> None:
    summary = evaluate_policy(_real_join(name, corpus)).summary

    assert summary.n_correct == correct
    assert summary.total_cost_usd == pytest.approx(cost, abs=5e-5)


@pytest.mark.skipif(not HAVE_DATA, reason="needs the git-ignored data/runs/cv1 dev runs")
def test_oracle_and_latency_rows_reproduce_on_d100() -> None:
    joined = _real_join("cascade_v1", "D100")

    oracle = evaluate_oracle(joined).summary
    cascade = evaluate_policy(joined).summary

    assert (oracle.n_correct, oracle.tier_calls["need-default"]) == (172, 39)
    assert cascade.latency_median_s == pytest.approx(2.3, abs=0.05)
    assert cascade.latency_p90_s == pytest.approx(52.0, abs=0.05)
