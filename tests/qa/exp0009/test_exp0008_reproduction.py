"""The two-step path (pool, then sample) reproduces EXP-0008's sealed sets byte for byte (T6b)."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.exp0009 import question_files as qf
from plantgraph.qa.exp0009.questions import SEALED, PlantPool
from plantgraph.qa.questions.availability import BinTargets
from plantgraph.qa.questions.sealed_set import build_pool

_ROOT = Path(__file__).resolve().parents[3] / "data" / "runs" / "exp0008"


@pytest.mark.parametrize("plant", ["H100g21p1", "H100g21p2"])
def test_exp0008_sealed_questions_reproduce(plant: str) -> None:
    ingest = _ROOT / "corpora" / plant / "ingest.json"
    stored = _ROOT / "questions" / plant / "questions.jsonl"
    if not ingest.is_file() or not stored.is_file():
        pytest.skip(f"EXP-0008's {plant} files are not on this machine")
    artifacts = load_corpus_artifacts(plant, ingest)
    targets = BinTargets(per_bin=SEALED.n_per_bin, unanswerable=SEALED.n_unanswerable)
    pool, _report = build_pool(artifacts, targets, SEALED.pool_seed)
    empty_drop = qf.DropSet(frozenset(), frozenset())
    drawn, _splits = qf.sample_r(PlantPool(pool, {}, {}, [], {}), empty_drop, SEALED)
    assert qf._jsonl(drawn) == stored.read_bytes()
