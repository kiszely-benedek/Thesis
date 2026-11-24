"""The loads, files only (no Neo4j): the Cypher copy is kept once; the B folder is a relabel."""

from __future__ import annotations

import json

import pytest
from exp0009_small import built_small

from plantgraph.qa.exp0009 import build, load


def test_a_load_keeps_one_cypher_copy_and_b_is_prepared_from_it() -> None:
    spec, corpora, _record = built_small()
    root = corpora.parent
    loaded = load.load_a(root, spec.plant_id, None)
    assert json.loads(loaded.read_text(encoding="utf-8"))["store_profile"] == "plant_lines"
    kept = root / load.CYPCORP / spec.plant_id / "ingest.json"
    first = kept.read_bytes()
    load.load_a(root, spec.plant_id, None)  # a reload rewrites neo4jplant/, never the kept copy
    assert kept.read_bytes() == first
    b_dir = load.prepare_b_load(root, spec.plant_id)
    build.require_relabel_equal(kept, b_dir / "ingest.json")
    assert (b_dir / "operating_positions.json").is_file()


def test_prepare_b_refuses_a_changed_positions_file() -> None:
    spec, corpora, _record = built_small()
    root = corpora.parent
    positions = corpora / spec.b_id / "operating_positions.json"
    original = positions.read_bytes()
    try:
        positions.write_bytes(original + b" ")
        with pytest.raises(ValueError, match="hash"):
            load.prepare_b_load(root, spec.plant_id)
    finally:
        positions.write_bytes(original)


def test_the_b_copy_keeps_a_load_report_and_relabels_only_the_top_level_id() -> None:
    kept = {"corpus_id": "D100g22", "config": {}, "load_report": {"corpus_id": "D100g22"}}
    text = json.dumps(kept, indent=2)
    out = load.relabel_top_level_id(text, "D100g22", "D100g22B")
    assert json.loads(out)["corpus_id"] == "D100g22B"
    assert json.loads(out)["load_report"]["corpus_id"] == "D100g22"
    assert out.count('"corpus_id": "D100g22B"') == 1


def test_the_top_level_relabel_refuses_a_file_without_the_leading_field() -> None:
    with pytest.raises(ValueError, match="start with"):
        load.relabel_top_level_id('{"x": 1, "corpus_id": "D100g22"}', "D100g22", "D100g22B")
