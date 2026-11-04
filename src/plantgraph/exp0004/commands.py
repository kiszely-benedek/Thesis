"""The six steps of the free path, each reading and writing files in one corpus directory."""

from __future__ import annotations

import json
from pathlib import Path

from plantgraph.exp0004 import storage
from plantgraph.exp0004.bootstrap import N_RESAMPLES
from plantgraph.exp0004.corpus import DEV_SEED, Corpus, CorpusSpec
from plantgraph.exp0004.deciders import DECIDER_IDS, DeciderRun, make_decider, run_decider
from plantgraph.exp0004.description import CorpusFile, describe
from plantgraph.exp0004.pairs import PairFile, build_pair_records
from plantgraph.exp0004.report import render_report
from plantgraph.exp0004.scoring import ScoreFile, score_corpus
from plantgraph.exp0004.tuning import Taus, TuningRow, tune
from plantgraph.resolution.identity_links import IdentityLinkSet


def build(spec: CorpusSpec, directory: Path) -> CorpusFile:
    """Build the corpus, label its candidate pairs, write `corpus.json` and `pairs.json`."""
    if storage.corpus_path(directory).exists():
        raise FileExistsError(
            f"expected no corpus in {directory} (a measurement is never overwritten)"
        )
    corpus = Corpus(spec)
    records = build_pair_records(corpus)
    corpus_file = CorpusFile(spec=spec, description=describe(corpus, records))
    storage.write_model(storage.corpus_path(directory), corpus_file)
    storage.write_model(
        storage.pairs_path(directory), PairFile(corpus_id=spec.corpus_id, pairs=records)
    )
    return corpus_file


def decide(directory: Path, decider_id: str, taus_json: Path | None = None) -> DeciderRun:
    """Run one decider on the corpus in `directory`; D1 and D2 take tau from `taus_json`."""
    corpus = rebuild(directory)
    run = run_decider(corpus, make_decider(decider_id, _threshold(decider_id, taus_json)))
    storage.write_model(storage.decision_path(directory, decider_id), run)
    return run


def tune_thresholds(directory: Path) -> Taus:
    """Tune D1 and D2 on the dev corpus in `directory`; refuses any other seed before building."""
    spec = storage.read_model(storage.corpus_path(directory), CorpusFile).spec
    if spec.seed != DEV_SEED:
        raise ValueError(
            f"expected the dev seed {DEV_SEED} to tune on, got {spec.seed}: tuning is dev only"
        )
    taus, trace = tune(rebuild(directory))
    storage.write_text(storage.taus_path(directory), taus.model_dump_json())
    storage.write_text(storage.trace_path(directory), _trace_json(trace))
    return taus


def score(directory: Path, n_resamples: int = N_RESAMPLES) -> ScoreFile:
    """Score every decision file in `directory` against the pair labels (no corpus rebuild)."""
    pair_file = storage.read_model(storage.pairs_path(directory), PairFile)
    runs = [
        storage.read_model(storage.decision_path(directory, decider_id), DeciderRun)
        for decider_id in DECIDER_IDS
        if storage.decision_path(directory, decider_id).exists()
    ]
    if not runs:
        raise FileNotFoundError(
            f"expected decision files in {directory}/decisions (run `decide`), found none"
        )
    result = score_corpus(pair_file.corpus_id, pair_file.pairs, runs, n_resamples)
    storage.write_model(storage.score_path(directory), result)
    return result


def write_links(directory: Path, decider_id: str, out: Path | None = None) -> Path:
    """Write the accepted links as an `IdentityLinkSet` JSON for `ingest --identity-links`."""
    run = storage.read_model(storage.decision_path(directory, decider_id), DeciderRun)
    target = out or storage.links_path(directory, decider_id)
    link_set: IdentityLinkSet = run.link_set
    storage.write_model(target, link_set)
    return target


def report(directories: list[Path], out: Path) -> None:
    """Write one Markdown report over the `score.json` of every directory."""
    scores = [storage.read_model(storage.score_path(d), ScoreFile) for d in directories]
    storage.write_text(out, render_report(scores))


def rebuild(directory: Path) -> Corpus:
    """Rebuild the corpus from its spec and check it is the one `build` labelled.

    Raises:
        ValueError: the rebuilt candidate pairs differ from `pairs.json`.
    """
    spec = storage.read_model(storage.corpus_path(directory), CorpusFile).spec
    corpus = Corpus(spec)
    stored = storage.read_model(storage.pairs_path(directory), PairFile).pairs
    if build_pair_records(corpus) != stored:
        raise ValueError(
            f"expected the rebuilt corpus to match {storage.pairs_path(directory)}, "
            "found a difference"
        )
    return corpus


def _threshold(decider_id: str, taus_json: Path | None) -> float | None:
    if decider_id == "d0":
        return None
    if taus_json is None:
        raise ValueError(
            f"expected --taus-json for decider {decider_id} (thresholds come from the dev corpus)"
        )
    taus = storage.read_model(taus_json, Taus)
    return taus.tau1 if decider_id == "d1" else taus.tau2


def _trace_json(trace: dict[str, list[TuningRow]]) -> str:
    return json.dumps(
        {name: [row.model_dump() for row in rows] for name, rows in trace.items()}, indent=1
    )
