"""Answer ChatP&ID's five EX01 questions with every arm, repeat by repeat (design §11, row E-T1).

The harness (`qa.harness`) needs a gold answer key and a split manifest, which a real imported
drawing does not have. So this runner reuses the harness's parts instead:
`registry.build_strategy` builds each arm, `attempt.run_unscored` answers one question without
scoring, `SpendGuard` caps the money.
Paid calls need `allow_paid_calls`; without it the run reads the caches only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel

from plantgraph.llm.models import ChatRequest, ChatResponse
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policy
from plantgraph.qa.chatpid_qa import file_sha256, load_chatpid_qa
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.cypher import CypherSource
from plantgraph.qa.exp0001.ex01_arms import build_arm_strategy, load_arm_record
from plantgraph.qa.exp0001.ex01_cascade import derive_cascade_rows, tier_arms
from plantgraph.qa.exp0001.ex01_models import (
    CASCADE_ARM,
    Ex01ArmRecord,
    Ex01Question,
    Ex01RunConfig,
)
from plantgraph.qa.exp0001.ex01_store import Ex01RunDir, row_key
from plantgraph.qa.exp0001.ex01_worker import PRIMER, RepeatWorker, spend_guard
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.cypher_setup import (
    CypherSourceFactory,
    check_store_profile,
    open_checked_neo4j_view,
)
from plantgraph.qa.harness.freeze import prompt_hashes, read_git_state
from plantgraph.qa.harness.spend_cap import SpendCapReached
from plantgraph.qa.strategies.cypher_rag import PROFILE_OF_NAME

CORPUS_ID = "EX01"
EXPERIMENT = "EXP-0001"
CASCADE_POLICY_FILE = POLICIES_DIR / "cascade_v3.json"
_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Ex01Settings:
    """Everything one `ex01` invocation is told on the command line."""

    out_dir: Path
    inputs_dir: Path
    corpora_root: Path
    qa_path: Path
    arms: list[str]
    repeats: int
    cap_usd: float | None
    allow_paid_calls: bool
    #: What the spend cap reserves for each question until real costs are known.
    cost_per_question_usd: float
    run_id: str = "E1-EX01"


class Ex01Summary(BaseModel):
    """What one invocation did, printed as JSON at the end."""

    run_id: str
    n_new_rows: int
    n_cascade_rows: int
    stopped_by_spend_cap: bool
    not_applicable: dict[str, str]
    spent_usd: float


def load_ex01_questions(qa_path: Path) -> list[Ex01Question]:
    """ChatP&ID's scored questions (CP11-CP15), wording unchanged.

    Raises:
        ValueError: the file does not hold exactly the five scored questions.
    """
    scored = [row for row in load_chatpid_qa(qa_path) if row.scope == "scored"]
    ids = [row.qid for row in scored]
    if ids != ["CP11", "CP12", "CP13", "CP14", "CP15"]:
        raise ValueError(f"expected the scored questions CP11..CP15 in {qa_path}, found {ids}")
    return [Ex01Question(row.qid, row.question) for row in scored]


def run_ex01(
    settings: Ex01Settings,
    *,
    http_client: httpx2.Client | None = None,
    progress: Callable[[str], None] = print,
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view,
) -> Ex01Summary:
    """Run (or resume) the EX01 arms; `http_client` is where tests inject the fake transport.

    Raises:
        CacheMiss: a replay (no `allow_paid_calls`) needs a response the cache does not hold.
        StoreMismatch: the Cypher arm is asked for and the database is not exactly EX01.
    """
    questions = load_ex01_questions(settings.qa_path)
    ingest_path = settings.corpora_root / CORPUS_ID / "ingest.json"
    artifacts = load_corpus_artifacts(CORPUS_ID, ingest_path)
    view = NetworkxGraphView(CORPUS_ID, artifacts.localized_sheets, artifacts.resolution)
    records = {name: load_arm_record(name, settings.inputs_dir) for name in settings.arms}
    source: CypherSource | None = None
    if any(r.strategy in PROFILE_OF_NAME for r in records.values()):
        check_store_profile(artifacts.load_plan, "plant")
        source = cypher_source_factory(artifacts.load_plan)
    try:
        records = _mark_not_applicable(records, view, source)
        config = _freeze(settings, records, questions, ingest_path)
        return _run_repeats(settings, config, questions, view, source, http_client, progress)
    finally:
        if source is not None:
            source.close()


def _refuse_send(request: ChatRequest) -> ChatResponse:
    raise RuntimeError("expected no model call while only building a strategy, found one")


def _mark_not_applicable(
    records: dict[str, Ex01ArmRecord], view: NetworkxGraphView, source: CypherSource | None
) -> dict[str, Ex01ArmRecord]:
    """Build every arm once with a sender that refuses calls; an arm that cannot build is N/A.

    The frozen code is never patched: an arm the registry cannot build over EX01 is reported
    "not applicable" with the reason, and the run goes on without it.
    """
    checked: dict[str, Ex01ArmRecord] = {}
    for name, record in records.items():
        cypher_source = source if record.strategy in PROFILE_OF_NAME else None
        try:
            build_arm_strategy(record, view, _refuse_send, cypher_source, PRIMER)
        except Exception as error:  # any build failure on EX01 is the finding (see docstring)
            record = record.model_copy(
                update={"not_applicable": f"{type(error).__name__}: {error}"}
            )
        checked[name] = record
    return checked


def _freeze(
    settings: Ex01Settings,
    records: dict[str, Ex01ArmRecord],
    questions: list[Ex01Question],
    ingest_path: Path,
) -> Ex01RunConfig:
    commit, dirty = read_git_state(_REPO_ROOT)
    config = Ex01RunConfig(
        run_id=settings.run_id,
        experiment=EXPERIMENT,
        created_at=datetime.now(UTC),
        git_commit=commit,
        git_dirty=dirty,
        corpus_id=CORPUS_ID,
        ingest_sha256=file_sha256(ingest_path),
        arms=records,
        repeats=settings.repeats,
        primer=PRIMER,
        prompt_hashes=prompt_hashes(),
        question_file=str(settings.qa_path),
        question_file_sha256=file_sha256(settings.qa_path),
        qids=[q.question_id for q in questions],
        cascade_policy=load_policy(CASCADE_POLICY_FILE).name,
        cascade_policy_sha256=file_sha256(CASCADE_POLICY_FILE),
        allow_paid_calls=settings.allow_paid_calls,
        cap_usd=settings.cap_usd,
    )
    return Ex01RunDir(settings.out_dir).freeze(config)


def _run_repeats(
    settings: Ex01Settings,
    config: Ex01RunConfig,
    questions: list[Ex01Question],
    view: NetworkxGraphView,
    source: CypherSource | None,
    http_client: httpx2.Client | None,
    progress: Callable[[str], None],
) -> Ex01Summary:
    run_dir = Ex01RunDir(settings.out_dir)
    run_dir.drop_provider_error_rows()  # a resume asks those items again
    rows = run_dir.read_rows()
    guard = spend_guard(
        settings.cap_usd, settings.allow_paid_calls, settings.cost_per_question_usd, rows
    )
    done = {row_key(row) for row in rows}
    n_new, stopped = 0, False
    for repeat in range(1, config.repeats + 1):
        worker = RepeatWorker(
            config,
            repeat,
            settings.out_dir,
            settings.allow_paid_calls,
            view,
            source,
            http_client,
            guard,
            done,
        )
        try:
            worker.answer_all(questions, run_dir, progress)
        except SpendCapReached as error:
            progress(f"STOPPED by the spend cap: {error}. Rerun with the same --out-dir to resume.")
            stopped = True
            break
        finally:
            n_new += worker.written
            worker.close()
    n_cascade = _write_cascade(config, run_dir, progress)
    return Ex01Summary(
        run_id=config.run_id,
        n_new_rows=n_new,
        n_cascade_rows=n_cascade,
        stopped_by_spend_cap=stopped,
        not_applicable={n: a.not_applicable for n, a in config.arms.items() if a.not_applicable},
        spent_usd=guard.spent_usd,
    )


def _write_cascade(
    config: Ex01RunConfig, run_dir: Ex01RunDir, progress: Callable[[str], None]
) -> int:
    """Append the derived cascade_v3 rows that are not on disk yet; returns how many."""
    policy = load_policy(CASCADE_POLICY_FILE)
    arms_needed = set(tier_arms(policy).values())
    usable = {n for n, a in config.arms.items() if a.not_applicable is None}
    if not arms_needed <= usable:
        progress(f"{CASCADE_ARM}: not derived, arms {sorted(arms_needed - usable)} did not run")
        return 0
    _check_tier_pins(policy, config)
    rows = run_dir.read_rows()
    have = {row_key(row) for row in rows}
    fresh = [r for r in derive_cascade_rows(rows, policy) if row_key(r) not in have]
    for row in fresh:
        run_dir.append_row(row)
    return len(fresh)


def _check_tier_pins(policy: CascadePolicy, config: Ex01RunConfig) -> None:
    """The arms must run under the pins the policy's tiers were frozen with."""
    arm_of_tier = tier_arms(policy)
    for tier in policy.tiers:
        found = config.arms[arm_of_tier[tier.name]].pin_sha256
        if found != tier.pin_sha256:
            raise ValueError(
                f"expected arm {arm_of_tier[tier.name]!r} to use pin {tier.pin_sha256} "
                f"(tier {tier.name!r} of {policy.name}), found {found}"
            )
