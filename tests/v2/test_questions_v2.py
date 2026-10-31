"""Question families on a v2 plant: the three v1-safe fixes (design vocabulary 7.4) and the walks.

A v2 plant draws things v1 never had: tees and fittings between two items, loops that are only
an indicator, a trip or a hand switch, a cascade, sensors on pipes, and tags like `P-1203A`.
"""

from __future__ import annotations

from collections.abc import Callable

import networkx as nx
import pytest
from corpus_v2 import corpus

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import Relation
from plantgraph.ingest.pipeline import SyntheticCorpus
from plantgraph.qa.harness.gold import _send_to_tag_edges
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.common import PATH_ITEM_CLASSES, is_path_item, next_path_items
from plantgraph.qa.questions.families import FAMILY_CANDIDATE_GENERATORS
from plantgraph.qa.questions.families_abstain import absent_tags
from plantgraph.qa.questions.families_flow import (
    flow_path_candidates,
    neighbours_downstream_candidates,
)
from plantgraph.qa.questions.families_heldout import HELDOUT_GENERATORS
from plantgraph.qa.questions.families_loop import (
    loop_actuated_valve_candidates,
    loop_measured_equipment_candidates,
)

_SEND_TO = Relation.SEND_TO.value
_SIGNAL = Relation.SEND_SIGNAL_TO.value
_CONTROL = Relation.CONTROL.value
_MEASURED_BY = Relation.MEASURED_BY.value

_Generator = Callable[..., list[Question]]
_Nodes = dict[str, tuple[str, str | None]]
_Edges = list[tuple[str, str, str]]


def _plant(nodes: _Nodes, edges: _Edges) -> nx.DiGraph[str]:
    """A one-sheet plant from `{id: (node_class, tag)}` and `[(source, target, relation)]`."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, (node_class, tag) in nodes.items():
        attrs = {"node_class": node_class, "unit_id": "1"}
        plant.add_node(node_id, **attrs, **({"tag": tag} if tag else {}))
    for source, target, relation in edges:
        plant.add_edge(source, target, relation=relation)
    return plant


def _ask(generator: _Generator, plant: nx.DiGraph[str]) -> list[Question]:
    sheet = SheetGraph(sheet_id="S1", graph=plant.copy())
    manifest = SplitManifest(source="test", sheet_files=["S1"])
    return generator(plant, manifest, [sheet], corpus_id="T", seed=1)


def _ask_corpus(generator: _Generator, built: SyntheticCorpus) -> list[Question]:
    return generator(built.plant, built.manifest, built.sheets, corpus_id="T", seed=1)


# --- every family generates on v2 ---------------------------------------------------------------


def test_every_dev_family_generates_candidates_on_a_v2_corpus() -> None:
    built = corpus()
    for family, generator in FAMILY_CANDIDATE_GENERATORS.items():
        assert _ask_corpus(generator, built), f"expected {family.value} to have candidates on v2"


@pytest.mark.parametrize("family", list(HELDOUT_GENERATORS))
def test_every_held_out_family_runs_on_a_v2_corpus_without_error(family: QuestionFamily) -> None:
    # FIRST_MEETING_POINT may be empty on v2: flows merge at tees, which are not items
    _ask_corpus(HELDOUT_GENERATORS[family], corpus(12))


def test_path_and_neighbour_answers_name_only_equipment_and_valves() -> None:
    built = corpus()
    tag_class = {a["tag"]: a["node_class"] for _, a in built.plant.nodes(data=True) if "tag" in a}
    for generator in (neighbours_downstream_candidates, flow_path_candidates):
        for question in _ask_corpus(generator, built):
            tags = question.reference
            assert isinstance(tags, list) and tags
            assert all(tag_class[tag] in PATH_ITEM_CLASSES for tag in tags), question.text


# --- walks look through unnamed fittings --------------------------------------------------------

_TEE_PLANT: tuple[_Nodes, _Edges] = (
    {
        "tank": ("Tank", "TK-101"),
        "tee": ("PipeTee", None),
        "valve": ("GateValve", "GTV-1101"),
        "pump": ("CentrifugalPump", "P-102"),
        "tee2": ("PipeTee", None),
        "drum": ("PressureVessel", "V-103"),
    },
    [
        ("tank", "tee", _SEND_TO),
        ("tee", "valve", _SEND_TO),
        ("tee", "pump", _SEND_TO),
        ("valve", "tee2", _SEND_TO),
        ("tee2", "drum", _SEND_TO),
    ],
)


def test_the_next_items_of_a_tank_are_found_through_its_tee() -> None:
    hops = {hop.item_id: hop.via for hop in next_path_items(_plant(*_TEE_PLANT), "tank")}
    assert hops == {"valve": ("tee",), "pump": ("tee",)}


def test_a_neighbours_question_lists_the_items_behind_a_tee() -> None:
    by_anchor = {
        q.anchors[0]: q for q in _ask(neighbours_downstream_candidates, _plant(*_TEE_PLANT))
    }
    assert by_anchor["TK-101"].reference == ["GTV-1101", "P-102"]
    assert by_anchor["GTV-1101"].reference == ["V-103"]
    assert set(by_anchor) == {"TK-101", "GTV-1101"}  # an untagged tee is never a subject


def test_a_flow_path_lists_the_items_and_skips_the_fittings_between_them() -> None:
    paths = {tuple(q.anchors): q.reference for q in _ask(flow_path_candidates, _plant(*_TEE_PLANT))}
    assert paths[("TK-101", "V-103")] == ["TK-101", "GTV-1101", "V-103"]


def test_a_path_answer_that_steps_over_a_tee_is_a_valid_edge() -> None:
    edges = _send_to_tag_edges(_plant(*_TEE_PLANT))
    assert ("TK-101", "GTV-1101") in edges and ("GTV-1101", "V-103") in edges
    assert ("TK-101", "V-103") not in edges  # two items apart is not one step


def test_only_equipment_and_valves_are_path_items() -> None:
    plant = _plant(*_TEE_PLANT)
    assert [n for n in plant.nodes if is_path_item(plant, n)] == ["tank", "valve", "pump", "drum"]


# --- loop families: the v2 loops that are not a full chain ---------------------------------------

_LOOPS: tuple[_Nodes, _Edges] = (
    {
        "tank": ("Tank", "TK-101"),
        "valve": ("GlobeValve", "FV-1101"),
        "pipe_valve": ("GateValve", "GTV-1102"),
        # a full loop: sensor on the tank, controller, valve actuator
        "s1": ("ProcessSignalGeneratingFunction", "LT-1101"),
        "c1": ("ProcessInstrumentationFunction", "LIC-1101"),
        "a1": ("ActuatingFunction", None),
        # indicator only: sensor on the tank, no valve
        "s2": ("ProcessSignalGeneratingFunction", "PT-1102"),
        "i2": ("ProcessInstrumentationFunction", "PI-1102"),
        # cascade: a sensor feeds the master, the master feeds a slave that also has a sensor
        "s3": ("ProcessSignalGeneratingFunction", "TT-1103"),
        "m3": ("ProcessControlFunction", "TIC-1103"),
        "s4": ("ProcessSignalGeneratingFunction", "FT-1103"),
        "l4": ("ProcessControlFunction", "FIC-1103"),
        "a4": ("ActuatingFunction", None),
        # a hand switch starting a motor: no sensor, no valve actuator
        "hs": ("ProcessInstrumentationFunction", "HS-1104"),
        "aef": ("ActuatingElectricalFunction", None),
        # a sensor on a pipe valve instead of on equipment
        "s5": ("ProcessSignalGeneratingFunction", "FT-1105"),
        "i5": ("ProcessInstrumentationFunction", "FI-1105"),
    },
    [
        ("tank", "s1", _MEASURED_BY),
        ("s1", "c1", _SIGNAL),
        ("c1", "a1", _SIGNAL),
        ("a1", "valve", _CONTROL),
        ("tank", "s2", _MEASURED_BY),
        ("s2", "i2", _SIGNAL),
        ("tank", "s3", _MEASURED_BY),
        ("s3", "m3", _SIGNAL),
        ("m3", "l4", _SIGNAL),
        ("tank", "s4", _MEASURED_BY),
        ("s4", "l4", _SIGNAL),
        ("l4", "a4", _SIGNAL),
        ("a4", "valve", _CONTROL),
        ("hs", "aef", _SIGNAL),
        ("aef", "tank", _CONTROL),
        ("pipe_valve", "s5", _MEASURED_BY),
        ("s5", "i5", _SIGNAL),
    ],
)


def test_the_actuated_valve_family_takes_only_controllers_with_exactly_one_valve_actuator() -> None:
    loops = {q.anchors[0] for q in _ask(loop_actuated_valve_candidates, _plant(*_LOOPS))}
    # the cascade master has no actuator; the indicators, the hand switch and the pipe sensor none
    assert loops == {"LIC-1101", "FIC-1103"}


def test_the_measured_equipment_family_takes_controllers_with_one_sensor_on_equipment() -> None:
    questions = _ask(loop_measured_equipment_candidates, _plant(*_LOOPS))
    answers = {q.anchors[0]: q.reference for q in questions}
    # the slave FIC-1103 has two signal predecessors but only one sensor; the hand switch has
    # none; FI-1105's sensor sits on a valve, not on equipment
    assert answers == {
        "LIC-1101": "TK-101",
        "PI-1102": "TK-101",
        "TIC-1103": "TK-101",
        "FIC-1103": "TK-101",
    }


# --- absent tags in both grammars ---------------------------------------------------------------


def test_absent_tags_follow_the_v2_grammar_per_prefix_and_unit_at_the_right_width() -> None:
    plant = _plant(
        {
            "p1": ("CentrifugalPump", "P-1203A"),
            "p2": ("CentrifugalPump", "P-1203B"),
            "p3": ("CentrifugalPump", "P-1207"),
            "k1": ("Tank", "TK-1202"),
            "v1": ("GateValve", "GTV-12107"),
            "v2": ("PressureVessel", "V-101"),  # unit 1, sequence 01
            "loop": ("ProcessInstrumentationFunction", "FIC-12014"),  # not equipment or valve
        },
        [],
    )
    # highest sequence + 1, same width: pumps of unit 12 07 -> 08, tanks 02 -> 03, valves 107 -> 108
    assert absent_tags(plant) == ["GTV-12108", "P-1208", "TK-1203", "V-102"]


def test_a_v2_group_at_the_widest_sequence_has_no_absent_tag() -> None:
    assert absent_tags(_plant({"p": ("CentrifugalPump", "P-1299")}, [])) == []


def test_absent_tags_keep_the_v1_grammar_for_v1_tags() -> None:
    plant = _plant({"v": ("GateValve", "GV-2-3"), "w": ("GateValve", "GV-2-11")}, [])
    assert absent_tags(plant) == ["GV-2-12"]


def test_a_v2_corpus_has_absent_tags_none_of_which_is_a_real_tag() -> None:
    built = corpus()
    real = {a["tag"] for _, a in built.plant.nodes(data=True) if "tag" in a}
    generated = absent_tags(built.plant)
    assert generated and not set(generated) & real


# --- FIRST_MEETING_POINT is excluded on v2 (ADR-0059 point 6) --------------------------------


def _count_enumeration_calls(monkeypatch: pytest.MonkeyPatch, v2: bool) -> list[int]:
    """Run `heldout_candidates` on a small plant; count FIRST_MEETING_POINT generator calls."""
    from plantgraph.qa.questions import families_heldout

    calls: list[int] = []

    def fake(*_args: object, **_kwargs: object) -> list[Question]:
        calls.append(1)
        return []

    patched = {**HELDOUT_GENERATORS, QuestionFamily.FIRST_MEETING_POINT: fake}
    monkeypatch.setattr(families_heldout, "HELDOUT_GENERATORS", patched)
    built = corpus(12)
    result = families_heldout.heldout_candidates(
        built.plant, built.manifest, built.sheets, corpus_id="T", seed=1, v2=v2
    )
    assert result[QuestionFamily.FIRST_MEETING_POINT] == []
    return calls


def test_first_meeting_point_is_not_enumerated_on_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _count_enumeration_calls(monkeypatch, v2=True) == []


def test_first_meeting_point_is_still_enumerated_on_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _count_enumeration_calls(monkeypatch, v2=False) == [1]
