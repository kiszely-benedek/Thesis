"""Does the demo's routed live cascade answer like the frozen offline walk? Asked for free.

Run as `python -m plantgraph.demo.app replay-agreement --corpus H100g21p1 --routed-only`.

The live cascade runs with paid calls switched off over a *copy* of the experiment's response
cache, so every model call is either a stored reply or a reported cache miss; nothing is sent.
Per question the result is compared with the offline walk the experiment scored: same final
tier, same outcome, same final answer. Questions routed past the database tier read only the
in-memory graph, so `--routed-only` needs no Neo4j.
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

import httpx2

from plantgraph.demo.app.need_routing import route_question, split_by_start
from plantgraph.demo.app.replay_models import (
    CorpusReplay,
    OfflineResult,
    ReplayRow,
    compare,
    offline_results,
    summarise,
)
from plantgraph.demo.app.replay_report import (
    ReplayReport,
    check_freeze,
    sha256_of,
    write_report,
)
from plantgraph.qa.cascade.evaluate import DEFAULT_CUTOFF_S
from plantgraph.qa.cascade.join import TierSource, join_corpus
from plantgraph.qa.cascade.labels import anchor_finder
from plantgraph.qa.cascade.live_build import OpenedCascade, open_live_cascade
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import load_policy
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import GraphView, NetworkxGraphView
from plantgraph.qa.harness.cypher_setup import CypherSourceFactory, open_checked_neo4j_view
from plantgraph.qa.harness.question_set import load_questions, questions_path
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.models import Question
from plantgraph.store.neo4j_plan import LoadPlan

_EXP = Path("data/runs/exp0008")
_DEFAULT_POLICY = Path("src/plantgraph/qa/cascade/policies_v2t/cascade_v4_iso.json")
#: Where each tier's source run lives; `{corpus}` is replaced by the corpus id.
_DEFAULT_TIER_RUNS = (
    f"cypher-v2t={_EXP}/m6a/runs/S7-CYP-{{corpus}}",
    f"agent-v2t={_EXP}/m6a/runs/S7-AG-{{corpus}}",
)


@dataclass(frozen=True)
class ReplaySetup:
    """Everything one corpus's replay needs, already loaded (so tests can build it by hand)."""

    corpus_id: str
    policy: CascadePolicy
    view: GraphView
    load_plan: LoadPlan | None
    tier_run_dirs: dict[str, Path]
    questions: list[Question]
    #: Offline result per question id; only these questions are replayed.
    offline: dict[str, OfflineResult]
    cutoff_s: float
    routed_only: bool
    #: The stored cache; only ever read (copied), never opened for writing.
    cache_source: Path
    #: Folder for the cache copy and the calls log; the caller deletes it.
    work_dir: Path
    cypher_source_factory: CypherSourceFactory = open_checked_neo4j_view
    #: Tests pass a client over a fake transport, to prove nothing is sent.
    http_client: httpx2.Client | None = None


def replay_corpus(setup: ReplaySetup) -> CorpusReplay:
    """Replay every question of `setup.offline` and compare with its offline result.

    Raises:
        FileNotFoundError: the cache does not exist.
        ValueError: the cache changed during the replay, or `routed_only` found no routed question.
    """
    if not setup.cache_source.is_file():
        raise FileNotFoundError(f"expected the stored cache at {setup.cache_source}, found none")
    before = sha256_of(setup.cache_source)
    cache_copy = setup.work_dir / "cache_copy.sqlite"
    shutil.copyfile(setup.cache_source, cache_copy)  # reads the original, writes only the copy
    rows = _replay_rows(setup, cache_copy)
    after = sha256_of(setup.cache_source)
    if after != before:
        raise ValueError(f"expected {setup.cache_source} unchanged, found its hash changed")
    if setup.routed_only and not any(row.routed for row in rows):
        raise ValueError(f"expected routed questions in {setup.corpus_id}, found none")
    return CorpusReplay(
        corpus_id=setup.corpus_id,
        policy=setup.policy.name,
        routed_only=setup.routed_only,
        cutoff_s=setup.cutoff_s,
        cache_source=str(setup.cache_source),
        cache_sha256_before=before,
        cache_sha256_after=after,
        rows=tuple(rows),
        **summarise(rows),
    )


def _replay_rows(setup: ReplaySetup, cache_copy: Path) -> list[ReplayRow]:
    routed = split_by_start(setup.policy)
    find_anchors = anchor_finder(setup.view)
    # `--routed-only` opens only the later-start cascades, which never touch the database
    starts = [s for s in routed.by_start if s > 0 or not setup.routed_only]
    rows: list[ReplayRow] = []
    with ExitStack() as stack:
        cascades = {
            start: stack.enter_context(_open_cascade(setup, routed.by_start[start], cache_copy))
            for start in starts
        }
        for question in setup.questions:
            offline = setup.offline.get(question.question_id)
            if offline is None:
                continue
            route = route_question(question.text, find_anchors, routed)
            if route.start_index not in cascades:
                raise ValueError(
                    f"expected {question.question_id} to be routed (start tier > 0), found it "
                    f"labelled {route.need_label.value} and starting at tier 0; it needs the "
                    "database, so run without --routed-only"
                )
            answer = cascades[route.start_index].cascade.ask(question)
            rows.append(
                compare(question.question_id, route.routed, offline, answer, route.need_label)
            )
    return rows


def _open_cascade(setup: ReplaySetup, policy: CascadePolicy, cache_copy: Path) -> OpenedCascade:
    """A cascade that may not pay: a missing reply comes back as `NeedsPaidCall`."""
    return open_live_cascade(
        corpus_id=setup.corpus_id,
        policy=policy,
        view=setup.view,
        load_plan=setup.load_plan,
        tier_run_dirs=setup.tier_run_dirs,
        cache_path=cache_copy,
        calls_log_path=setup.work_dir / "calls.jsonl",
        allow_paid_calls=False,
        cutoff_s=setup.cutoff_s,
        guard=SpendGuard(None),
        cypher_source_factory=setup.cypher_source_factory,
        http_client=setup.http_client,
    )


def build_setup(args: argparse.Namespace, corpus_id: str, work_dir: Path) -> ReplaySetup:
    """Load the corpus, join the stored tier runs and compute the offline walk."""
    policy = load_policy(args.policy)
    tier_runs = _tier_run_dirs(args.tier_run, corpus_id)
    ingest = args.corpora_root / corpus_id / "ingest.json"
    artifacts = load_corpus_artifacts(corpus_id, ingest)
    view = NetworkxGraphView(corpus_id, artifacts.localized_sheets, artifacts.resolution)
    joined = join_corpus(
        policy,
        {tier: TierSource(run_dir) for tier, run_dir in tier_runs.items()},
        corpus_id,
        args.questions_root,
        anchor_finder(view),  # as R5 / EXP-0008 scored it
    )
    ids = [
        qid
        for qid in joined.question_ids
        if not args.routed_only or policy.start_tier_by_label.get(joined.need_labels[qid], 0) > 0
    ]
    return ReplaySetup(
        corpus_id=corpus_id,
        policy=policy,
        view=view,
        load_plan=artifacts.load_plan,
        tier_run_dirs=tier_runs,
        questions=load_questions(questions_path(args.questions_root, corpus_id), corpus_id),
        offline=offline_results(joined, ids, args.cutoff_s),
        cutoff_s=args.cutoff_s,
        routed_only=args.routed_only,
        cache_source=args.cache,
        work_dir=work_dir,
    )


def _tier_run_dirs(values: Sequence[str], corpus_id: str) -> dict[str, Path]:
    dirs: dict[str, Path] = {}
    for value in values:
        tier, separator, template = value.partition("=")
        if not separator or not tier:
            raise SystemExit(f"error: expected --tier-run TIER=DIR, found {value!r}")
        dirs[tier] = Path(template.format(corpus=corpus_id))
    return dirs


def build_parser() -> argparse.ArgumentParser:
    """The command line of `replay-agreement`."""
    parser = argparse.ArgumentParser(prog="replay-agreement", description=__doc__)
    parser.add_argument("--corpus", action="append", required=True, help="repeat for more plants")
    parser.add_argument("--routed-only", action="store_true", help="only routed questions")
    parser.add_argument("--policy", type=Path, default=_DEFAULT_POLICY)
    parser.add_argument("--cache", type=Path, default=_EXP / "m6a" / "cache.sqlite")
    parser.add_argument("--corpora-root", type=Path, default=_EXP / "corpora")
    parser.add_argument("--questions-root", type=Path, default=_EXP / "questions")
    parser.add_argument(
        "--tier-run",
        action="append",
        default=list(_DEFAULT_TIER_RUNS),
        help="TIER=DIR, with {corpus} in DIR; repeat per tier",
    )
    parser.add_argument("--cutoff-s", type=float, default=DEFAULT_CUTOFF_S)
    parser.add_argument("--freeze-list", type=Path, default=_EXP / "prereg" / "E9.sha256")
    parser.add_argument("--out", type=Path, default=_EXP / "demo" / "replay_agreement")
    return parser


def _refuse_output_beside_cache(out: Path, cache: Path) -> None:
    """The stored runs are evidence: never write a report into the cache's own folder."""
    if out.resolve().is_relative_to(cache.resolve().parent):
        raise SystemExit(f"error: expected --out outside {cache.parent}, found {out}")


def run_replay_agreement(argv: Sequence[str]) -> ReplayReport:
    """Replay each corpus, write the JSON and Markdown report, and print where they are."""
    args = build_parser().parse_args(list(argv))
    _refuse_output_beside_cache(args.out, args.cache)
    replays = []
    for corpus_id in args.corpus:
        work_dir = Path(tempfile.mkdtemp(prefix="replay-agreement-"))
        try:
            replays.append(replay_corpus(build_setup(args, corpus_id, work_dir)))
        finally:
            shutil.rmtree(work_dir)
    report = ReplayReport(freeze=check_freeze(args.freeze_list, Path.cwd()), corpora=tuple(replays))
    json_path, markdown_path = write_report(report, args.out)
    print(f"wrote {json_path} and {markdown_path}")
    return report
