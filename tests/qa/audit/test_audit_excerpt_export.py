"""The plant excerpt: the export script on a v2.1 plant, then the renderer on its output (F14)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import networkx as nx
import pytest

from audit_fakes import make_subgraph
from plantgraph.ingest.headline_v2 import HeadlinePresetV2
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.qa.audit.excerpt import (
    ExcerptTooLarge,
    QuestionSubgraph,
    SubgraphFile,
    SubgraphNode,
    render_excerpt,
)
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.questions.common import is_path_item, next_path_items

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_export_subgraphs.py"
_CORPUS_ID = "audit-fixture"
_NODE_ID = re.compile(r"\bu\d+-t\d+\b")  # the fixture's internal node ids, e.g. u1-t26


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("audit_export_subgraphs", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_export_subgraphs"] = module
    spec.loader.exec_module(module)
    return module


export = _load_script()


@pytest.fixture(scope="module")
def corpus_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A real v2.1 plant (6 units, seed 1), ingested without Neo4j and saved as `ingest.json`."""
    preset = HeadlinePresetV2(duplication_rate=1.0)
    result = run_synthetic(
        corpus_id=_CORPUS_ID,
        generator_config=preset.generator_config(6, 1),
        split_config=preset.split_config(1),
        check=True,
        settings=None,
        store_profile="plant",
    )
    folder = tmp_path_factory.mktemp("corpus")
    (folder / "ingest.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return folder


@pytest.fixture(scope="module")
def plant(corpus_dir: Path) -> nx.DiGraph[str]:
    loaded = load_corpus_artifacts(_CORPUS_ID, corpus_dir / "ingest.json").gold.plant
    assert loaded is not None
    return loaded


def _question_across_fittings(plant: nx.DiGraph[str]) -> tuple[dict[str, Any], list[str]]:
    """A question whose two evidence items are joined by at least two unnamed fittings."""
    for node_id, data in plant.nodes(data=True):
        if "tag" not in data or not is_path_item(plant, node_id):
            continue
        for hop in next_path_items(plant, node_id):
            if len(hop.via) >= 2:
                tags = [data["tag"], plant.nodes[hop.item_id]["tag"]]
                question = {"question_id": "q1", "corpus_id": _CORPUS_ID, "evidence_tags": tags}
                return question, list(hop.via)
    raise AssertionError("expected the fixture plant to have two items joined by two fittings")


def test_export_keeps_the_fittings_between_the_evidence_items(plant: nx.DiGraph[str]) -> None:
    question, fittings = _question_across_fittings(plant)

    exported = export.subgraph_for_question(plant, question)

    by_id = {node["id"]: node for node in exported["nodes"]}
    assert set(fittings) <= by_id.keys()
    assert all(by_id[f]["distance"] == 0 and by_id[f]["tag"] is None for f in fittings)
    assert set(exported["evidence_ids"]) <= by_id.keys()


def test_export_leaves_out_generator_bookkeeping(plant: nx.DiGraph[str]) -> None:
    question, _ = _question_across_fittings(plant)

    exported = export.subgraph_for_question(plant, question)

    text = json.dumps(exported)
    for internal in ("drawing_group", "sheet_group", "stream_kind", '"role"', "plant_id"):
        assert internal not in text


def test_export_refuses_an_evidence_tag_missing_from_the_plant(plant: nx.DiGraph[str]) -> None:
    question = {"question_id": "q", "corpus_id": "c", "evidence_tags": ["NO-SUCH-TAG"]}

    with pytest.raises(ValueError, match="NO-SUCH-TAG"):
        export.subgraph_for_question(plant, question)


def test_rendered_export_shows_fittings_as_numbered_untagged_parts(
    plant: nx.DiGraph[str],
) -> None:
    question, fittings = _question_across_fittings(plant)
    exported = export.subgraph_for_question(plant, question)

    text = render_excerpt(QuestionSubgraph.model_validate(exported))

    assert text.count("(untagged PipeTee #") >= len(fittings)
    assert not _NODE_ID.search(text)  # no internal id leaks into the text the judge reads


def test_main_writes_a_file_the_renderer_reads(corpus_dir: Path, plant: nx.DiGraph[str]) -> None:
    question, _ = _question_across_fittings(plant)
    questions = corpus_dir / "questions.jsonl"
    questions.write_text(json.dumps(question) + "\n", encoding="utf-8")
    ids = corpus_dir / "ids.txt"
    ids.write_text("q1\n", encoding="utf-8")
    out = corpus_dir / "out.json"

    status = export.main(
        ["--corpus-id", _CORPUS_ID, "--ingest-json", str(corpus_dir / "ingest.json")]
        + ["--questions", str(questions), "--question-ids", str(ids), "--out", str(out)]
    )

    parsed = SubgraphFile.model_validate_json(out.read_text(encoding="utf-8"))
    assert status == 0 and [s.question_id for s in parsed.subgraphs] == ["q1"]


def test_select_questions_refuses_a_wanted_id_that_is_not_in_the_file() -> None:
    with pytest.raises(ValueError, match="missing"):
        export.select_questions(['{"question_id": "a"}'], ["b"])


def test_render_cuts_the_far_parts_first_and_says_so() -> None:
    near = make_subgraph("q")
    far = [
        SubgraphNode(id=f"x{i}", node_class="Tank", tag=f"TK-{i}", distance=2) for i in range(20)
    ]
    subgraph = near.model_copy(update={"nodes": [*near.nodes, *far]})
    budget = len(render_excerpt(near)) + 120  # the four route parts, TK-9 and a few more

    short = render_excerpt(subgraph, max_chars=budget)

    assert len(short) <= budget
    assert "V-1" in short and "TK-9" in short and "TK-19" not in short
    assert "more distant parts left out" in short


def test_render_refuses_when_the_evidence_alone_does_not_fit() -> None:
    with pytest.raises(ExcerptTooLarge, match="do not"):
        render_excerpt(make_subgraph("q"), max_chars=50)
