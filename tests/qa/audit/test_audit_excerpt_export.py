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


# --- routes of a count question ----------------------------------------------------------------

_ITEMS = frozenset({"CentrifugalPump", "GateValve", "Tank", "HeatExchanger"})
_VALVES = frozenset({"GateValve"})
_COUNT_QUESTION: dict[str, Any] = {
    "question_id": "q-count",
    "corpus_id": _CORPUS_ID,
    "family": "VALVES_ON_PATH",
    "evidence_tags": ["P-1", "V-1", "V-2", "TK-9"],
    "anchors": ["P-1", "TK-9"],
}


def _three_route_plant(with_exchanger_branch: bool = True) -> nx.DiGraph[str]:
    """P-1 to TK-9 three ways: two valves and no fitting; one valve; one exchanger and no valve.

    The two-valve route has the fewest parts (4). The other two pass one item each, so they tie
    on items and differ in valves (1 and 0).
    """
    plant: nx.DiGraph[str] = nx.DiGraph()
    tagged = {
        "p1": ("CentrifugalPump", "P-1", "1"),
        "v1": ("GateValve", "V-1", "1"),
        "v2": ("GateValve", "V-2", "2"),
        "v3": ("GateValve", "V-3", "2"),
        "e1": ("HeatExchanger", "E-1", "2"),
        "t9": ("Tank", "TK-9", "2"),
    }
    for node_id, (node_class, tag, unit) in tagged.items():
        plant.add_node(node_id, node_class=node_class, tag=tag, unit_id=unit)
    for node_id in ("f1", "f2", "f3", "f4", "f5", "f6", "f7"):
        plant.add_node(node_id, node_class="PipeTee", unit_id="2")
    routes = [["p1", "v1", "v2", "t9"], ["p1", "f1", "f2", "v3", "f3", "t9"]]
    if with_exchanger_branch:
        routes.append(["p1", "f4", "f5", "e1", "f6", "f7", "t9"])
    for route in routes:
        nx.add_path(plant, route, relation="send_to")
    return plant


def test_a_count_question_gets_every_reading_of_its_route() -> None:
    plant = _three_route_plant()

    routes = export.anchor_routes(plant, _COUNT_QUESTION, _ITEMS, _VALVES)

    assert [r["node_ids"] for r in routes] == [
        ["p1", "v1", "v2", "t9"],
        ["p1", "f4", "f5", "e1", "f6", "f7", "t9"],
        ["p1", "f1", "f2", "v3", "f3", "t9"],
    ]
    assert [export.valves_between(plant, r["node_ids"], _VALVES) for r in routes] == [2, 0, 1]
    assert "fewest parts of any kind" in routes[0]["basis"]
    assert routes[1]["basis"].endswith("fewest valves")
    assert routes[2]["basis"].endswith("most valves")


def test_routes_that_tie_on_items_and_valves_are_one_reading() -> None:
    plant = _three_route_plant(with_exchanger_branch=False)

    routes = export.anchor_routes(plant, _COUNT_QUESTION, _ITEMS, _VALVES)

    assert [r["node_ids"][1] for r in routes] == ["v1", "f1"]
    assert "several such routes" not in routes[1]["basis"]


def test_one_route_under_both_readings_is_exported_once() -> None:
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("p1", node_class="CentrifugalPump", tag="P-1")
    plant.add_node("v1", node_class="GateValve", tag="V-1")
    plant.add_node("t9", node_class="Tank", tag="TK-9")
    nx.add_path(plant, ["p1", "v1", "t9"], relation="send_to")

    routes = export.anchor_routes(plant, _COUNT_QUESTION, _ITEMS, _VALVES)

    assert len(routes) == 1 and routes[0]["node_ids"] == ["p1", "v1", "t9"]
    assert "fewest parts" in routes[0]["basis"] and "; also " in routes[0]["basis"]


def test_no_route_is_exported_for_another_family_or_a_pair_with_no_flow_path() -> None:
    plant = _three_route_plant()
    other_family = {**_COUNT_QUESTION, "family": "FLOW_PATH"}
    against_the_flow = {**_COUNT_QUESTION, "anchors": ["TK-9", "P-1"]}
    unknown_tag = {**_COUNT_QUESTION, "anchors": ["P-1", "TK-404"]}

    for question in (other_family, against_the_flow, unknown_tag):
        assert export.anchor_routes(plant, question, _ITEMS, _VALVES) == []


def _count_subgraph() -> QuestionSubgraph:
    plant = _three_route_plant()
    routes = export.anchor_routes(plant, _COUNT_QUESTION, _ITEMS, _VALVES)
    exported = export.subgraph_for_question(plant, _COUNT_QUESTION, radius=1, routes=routes)
    return QuestionSubgraph.model_validate(exported)


def test_the_routes_are_written_out_before_the_parts_one_tagged_part_a_line() -> None:
    subgraph = _count_subgraph()

    text = render_excerpt(subgraph)

    routes_block, parts_block = text.split("Parts (*", maxsplit=1)
    assert routes_block.startswith("Routes from P-1 to TK-9")
    assert "Route 1: the route with the fewest parts of any kind (4 tagged parts):" in text
    assert "in unit 1:\n1. P-1 [CentrifugalPump]\n2. V-1 [GateValve]\nin unit 2:\n3. V-2" in text
    assert "untagged PipeTee" not in routes_block  # fittings are left out of a route
    assert "(untagged PipeTee #1)" in parts_block  # and still shown among the parts
    assert all(node.distance == 0 for node in subgraph.nodes)  # every route part is core


def test_a_tight_budget_keeps_the_routes_and_cuts_the_parts() -> None:
    subgraph = _count_subgraph()
    routes_only = len(render_excerpt(subgraph).split("Parts (*")[0])

    short = render_excerpt(subgraph, max_chars=routes_only + 150)

    assert short.count("Route ") == 3 and "2. E-1 [HeatExchanger]" in short
    assert "more distant parts left out" in short
    with pytest.raises(ExcerptTooLarge, match="found 3 routes"):
        render_excerpt(subgraph, max_chars=routes_only - 1)
