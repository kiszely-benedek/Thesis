"""The offline cascade per arm: accuracy per family over every family a question file holds (§19.7).

A **cascade** asks the cheap Cypher tier first and falls back to the agent tier when the first
answer is not accepted; the *policy* says how. A2 runs `cascade_v4_iso`, B runs `policy_b()` (the
same rules, reading the B strategy names), and the GLM arm runs `policy_glm()` (the same rules,
checked against GLM's model pins instead of Luna's). This is the frozen offline evaluation of
`qa/cascade/tune_report.py` for one policy. `qa.cascade tune-report` is not used, because it
compares two policies and does not know the scope X families.

The result feeds gates G1, G1-B and G1-B2 (`gates.py`) and the per-round tuning report.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.corpus_checks import load_corpus_view
from plantgraph.qa.cascade.evaluate import evaluate_policy
from plantgraph.qa.cascade.join import TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.labels import anchor_finder
from plantgraph.qa.cascade.limits import SETTING_A, LimitSetting, run_problems
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policies
from plantgraph.qa.cascade.report_groups import DIM_FAMILY, breakdown, question_groups
from plantgraph.qa.exp0009.glm_policy import policy_glm
from plantgraph.qa.v2tb.policy_b import policy_b

Arm = Literal["A2", "B", "GLM"]
A2_POLICY = "cascade_v4_iso"


class ArmReport(BaseModel):
    """One arm's cascade on one plant: totals and (correct, total) per family."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    arm: Arm
    policy: str
    n_questions: int
    n_correct: int
    by_family: dict[str, tuple[int, int]]
    correct_ids: tuple[str, ...]

    def accuracy(self, families: frozenset[str] | None = None) -> float:
        """Correct over total, over the given families (all, if none are given)."""
        cells = [c for f, c in self.by_family.items() if families is None or f in families]
        total = sum(t for _c, t in cells)
        return sum(c for c, _t in cells) / total if total else 0.0


def policy_of(arm: Arm) -> CascadePolicy:
    """`cascade_v4_iso` for A2, `policy_b()` for B, `policy_glm()` for the GLM arm.

    Raises:
        ValueError: an unknown arm.
    """
    if arm == "A2":
        return load_policies(V2T_POLICIES_DIR)[A2_POLICY]
    if arm == "B":
        return policy_b()
    if arm == "GLM":
        return policy_glm()
    raise ValueError(f"expected arm 'A2', 'B' or 'GLM', found {arm!r}")


def build_arm_report(
    corpus_id: str,
    arm: Arm,
    sources: Mapping[str, TierSource],
    questions_root: Path,
    corpora_root: Path,
    setting: LimitSetting = SETTING_A,
) -> ArmReport:
    """Join the arm's two tier runs, check them against `setting`, evaluate, count per family.

    Raises:
        ValueError: a run does not match the setting (the message lists the mismatches).
        JoinRefused / IncompleteJoinError: the runs differ from each other or lack a row.
    """
    policy = policy_of(arm)
    _path, questions = load_questions_file(questions_root, corpus_id)
    finder = anchor_finder(load_corpus_view(corpora_root, corpus_id))
    joined = join_corpus(policy, dict(sources), corpus_id, questions_root, finder)
    problems = run_problems(setting, joined.runs)
    if problems:
        raise ValueError("expected runs that match the setting, found:\n  " + "\n  ".join(problems))
    require_complete(joined)
    evaluation = evaluate_policy(joined, setting.cutoff_s)
    family_of = question_groups(questions, {})[DIM_FAMILY]
    cells = breakdown({policy.name: evaluation}, family_of, DIM_FAMILY)
    return ArmReport(
        corpus_id=corpus_id,
        arm=arm,
        policy=policy.name,
        n_questions=len(questions),
        n_correct=evaluation.summary.n_correct,
        by_family={f: (c[policy.name].correct, c[policy.name].total) for f, c in cells.items()},
        correct_ids=tuple(s.decision.question_id for s in evaluation.scored if s.correct),
    )
