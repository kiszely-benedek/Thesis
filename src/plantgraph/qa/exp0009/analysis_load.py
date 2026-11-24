"""Loading the sealed runs: each arm on each plant, joined and evaluated offline.

Only saved files are read (question files, run folders, `state/b_sealed`); no model is called and
no database is opened. The cascade is the frozen offline evaluation of `qa/cascade/`: the two tier
runs of a plant are joined, checked against setting A (30 s Cypher timeout, 120 s cutoff) and
scored per question.

A plant has two corpus ids. The **A id** (`H100g22p1`) is what V2T-A2 was asked on; the **B id**
(`H100g22p1B`) is the same plant for V2T-B. A **tier** is one model call stage of the cascade: the
Cypher tier answers first, the agent tier is the fallback.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.cascade.corpus_checks import load_corpus_view
from plantgraph.qa.cascade.evaluate import Evaluation, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.labels import AnchorFinder, anchor_finder, labels_from_run_dirs
from plantgraph.qa.cascade.limits import SETTING_A, run_problems
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, V2T_REFERENCES_DIR, load_policies
from plantgraph.qa.exp0009 import stages
from plantgraph.qa.exp0009.plan import PlantSpec22
from plantgraph.qa.models import Question
from plantgraph.qa.questions.per_family import read_questions
from plantgraph.qa.v2tb.policy_b import policy_b

QUESTIONS_FILE, SPLITS_FILE = "questions.jsonl", "splits.json"
RUN_PREFIX = "S9"  # the sealed runs of P1c: `S9-CYP-<id>`, `S9-AG-<id>B`
#: the tier names inside the V2T cascade policies, and the run-name part each tier uses
TIER_RUNS = {"cypher-v2t": "CYP", "agent-v2t": "AG"}
A2_PRIMARY = "cascade_v4_iso"
#: the policies the A2 claims read: the tested cascade, its unrouted sibling (K2) and the references
A2_POLICIES = ("cascade_v4_iso", "cascade_v4", "always_g_v2t", "always_c_v2t")

#: corpus id -> how to find anchors (tags, units) in its question texts; `None` = no graph needed
FinderFactory = Callable[[str], AnchorFinder | None]


@dataclass(frozen=True)
class ArmRuns:
    """One arm on one plant: its policies joined to the stored tier runs and evaluated."""

    corpus_id: str
    run_ids: tuple[str, ...]
    joins: Mapping[str, JoinedCorpus]
    #: policy name -> evaluation over every question of the arm's file
    evaluations: Mapping[str, Evaluation]


@dataclass(frozen=True)
class PlantData:
    """A sealed plant: its question files, A2's runs and (if B ran sealed) B's runs."""

    spec: PlantSpec22
    a2_questions: tuple[Question, ...]
    a2_splits: Mapping[str, str]
    b_questions: tuple[Question, ...]
    b_splits: Mapping[str, str]
    a2: ArmRuns
    b: ArmRuns | None


def corpus_finder(corpora_root: Path) -> FinderFactory:
    """Anchors found in the corpus graph rebuilt from `<corpora_root>/<id>/ingest.json`."""

    def factory(corpus_id: str) -> AnchorFinder:
        return anchor_finder(load_corpus_view(corpora_root, corpus_id))

    return factory


def read_b_sealed(root: Path) -> bool:
    """Whether B ran sealed: `state/b_sealed` says `yes` or `no` (written by P1b).

    Raises:
        ValueError: the file is missing or says something else.
    """
    path = root / "state" / "b_sealed"
    if not path.is_file():
        raise ValueError(f"expected {path} (P1b writes it), found none")
    text = path.read_text(encoding="utf-8").strip()
    if text not in ("yes", "no"):
        raise ValueError(f"expected 'yes' or 'no' in {path}, found {text!r}")
    return text == "yes"


def a2_policies() -> list[CascadePolicy]:
    """The four policies the A2 claims read, from the V2T policy files."""
    available = {**load_policies(V2T_POLICIES_DIR), **load_policies(V2T_REFERENCES_DIR)}
    return [available[name] for name in A2_POLICIES]


def tier_run_dirs(runs_dir: Path, corpus_id: str) -> dict[str, Path]:
    """`{'cypher-v2t': <runs>/S9-CYP-<id>, 'agent-v2t': <runs>/S9-AG-<id>}`.

    Raises:
        FileNotFoundError: a run folder is missing (the run did not finish).
    """
    dirs = {
        tier: runs_dir / stages.run_id(RUN_PREFIX, corpus_id, part)
        for tier, part in TIER_RUNS.items()
    }
    missing = [str(path) for path in dirs.values() if not path.is_dir()]
    if missing:
        raise FileNotFoundError(f"expected the run folders of {corpus_id}, missing {missing}")
    return dirs


def load_arm(
    corpus_id: str,
    tier_dirs: Mapping[str, Path],
    policies: Sequence[CascadePolicy],
    questions_root: Path,
    find_anchors: AnchorFinder | None,
) -> ArmRuns:
    """Join every policy to the tier runs, check setting A and completeness, evaluate.

    Raises:
        ValueError: a run does not match setting A (the message lists the mismatches).
        JoinRefused / IncompleteJoinError: the runs differ from each other or lack a row.
    """
    sources = {tier: TierSource(path) for tier, path in tier_dirs.items()}
    known = labels_from_run_dirs(tier_dirs.values())
    joins: dict[str, JoinedCorpus] = {}
    evaluations: dict[str, Evaluation] = {}
    for policy in policies:
        joined = join_corpus(policy, sources, corpus_id, questions_root, find_anchors, known)
        _require_setting_a(joined)
        require_complete(joined)
        joins[policy.name] = joined
        evaluations[policy.name] = evaluate_policy(joined, SETTING_A.cutoff_s)
    return ArmRuns(corpus_id, tuple(p.name for p in tier_dirs.values()), joins, evaluations)


def _require_setting_a(joined: JoinedCorpus) -> None:
    problems = run_problems(SETTING_A, joined.runs)
    if problems:
        raise ValueError(
            f"expected runs that match setting A for {joined.policy.name!r} on "
            f"{joined.corpus_id!r}, found:\n  " + "\n  ".join(problems)
        )


def read_question_files(
    questions_root: Path, corpus_id: str
) -> tuple[tuple[Question, ...], dict[str, str]]:
    """A corpus's questions and its `splits.json` (question id -> split name)."""
    folder = questions_root / corpus_id
    questions, _lines = read_questions(folder / QUESTIONS_FILE)
    splits = json.loads((folder / SPLITS_FILE).read_text(encoding="utf-8"))
    return tuple(questions), splits


def load_plant(
    root: Path, spec: PlantSpec22, b_sealed: bool, finder_for: FinderFactory
) -> PlantData:
    """One sealed plant: both question files, A2's evaluated runs, B's when B ran sealed."""
    questions_root, runs_dir = root / "questions", root / "p1c" / "runs"
    a2_q, a2_splits = read_question_files(questions_root, spec.plant_id)
    b_q, b_splits = read_question_files(questions_root, spec.b_id)
    # B's corpus is A's relabelled (same graph), so one anchor finder serves both arms
    finder = finder_for(spec.plant_id)
    a2 = load_arm(
        spec.plant_id, tier_run_dirs(runs_dir, spec.plant_id), a2_policies(), questions_root, finder
    )
    b = None
    if b_sealed:
        b_dirs = tier_run_dirs(runs_dir, spec.b_id)
        b = load_arm(spec.b_id, b_dirs, [policy_b()], questions_root, finder)
    return PlantData(spec, a2_q, a2_splits, b_q, b_splits, a2, b)
