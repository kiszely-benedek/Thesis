"""Task T6 (design 5, 8, 18.2): documents and the conventions a document keeps on every sheet.

A document is a run of `trains_per_area` trains. The plants are about 30 sheets (one document with
the default knobs); a small `trains_per_area` splits them into several documents.
"""

from __future__ import annotations

from dataclasses import replace
from functools import cache

import pytest
from plant_invariants import plant_view
from t9_support import SEEDS, units_for_30_sheets

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.documents import document_of_train, draw_documents
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_documents import (
    check_document_conventions,
    document_of_node,
)
from plantgraph.benchmark.v2.rules.control_graph import is_control_valve
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.benchmark.v2.vocabulary import MANUAL_VALVE_CLASSES, SpareNaming
from plantgraph.graph.schema import VALVE_CLASSES, Relation

_CONTROL = Relation.CONTROL.value


@cache
def _view(seed: int, per_document: int = 10, untagged: tuple[bool, ...] | None = None) -> RuleView:
    knobs = HandbookKnobs(trains_per_area=per_document, document_untagged=untagged)
    config = GeneratorConfigV22(seed=seed, n_units=units_for_30_sheets(seed), handbook=knobs)
    return build_rule_view(generate_plant_v2(config))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _has_actuator(view: RuleView, node: str) -> bool:
    return any(d["relation"] == _CONTROL for *_, d in view.graph.in_edges(node, data=True))


def _manual_valves(view: RuleView) -> list[str]:
    return [
        n
        for n, d in view.graph.nodes(data=True)
        if d["node_class"] in MANUAL_VALVE_CLASSES and not _has_actuator(view, n)
    ]


# ---- the draws -----------------------------------------------------------------------------------


def test_a_document_is_a_run_of_trains_and_depends_on_the_train_alone() -> None:
    assert [document_of_train(t, 3) for t in range(1, 8)] == [1, 1, 1, 2, 2, 2, 3]


def test_a_documents_draws_do_not_depend_on_how_many_trains_the_plant_has() -> None:
    config = GeneratorConfigV22(seed=3, n_units=1, handbook=HandbookKnobs(trains_per_area=2))
    short, long = draw_documents(config, 4), draw_documents(config, 12)
    assert short[0] == long[0] and short[1].conventions == long[1].conventions
    assert long[-1].last_train == 12 and short[-1].last_train == 4


def test_the_untagged_share_follows_its_declared_probability() -> None:
    config = GeneratorConfigV22(seed=1, n_units=1, handbook=HandbookKnobs(trains_per_area=1))
    untagged = sum(d.manual_valves_untagged for d in draw_documents(config, 400))
    assert 0.65 < untagged / 400 < 0.85  # the declared 0.75


@pytest.mark.parametrize(("p", "expected"), [(0.0, False), (1.0, True)])
def test_the_probability_forces_the_alternative(p: float, expected: bool) -> None:
    knobs = HandbookKnobs(trains_per_area=1, p_untagged_manual_document=p)
    documents = draw_documents(GeneratorConfigV22(seed=2, n_units=1, handbook=knobs), 20)
    assert {d.manual_valves_untagged for d in documents} == {expected}


def test_the_stratified_allocation_replaces_the_draw() -> None:
    flags = (True, False, False, True)
    knobs = HandbookKnobs(trains_per_area=1, document_untagged=flags)
    documents = draw_documents(GeneratorConfigV22(seed=2, n_units=1, handbook=knobs), 4)
    assert tuple(d.manual_valves_untagged for d in documents) == flags


def test_the_allocation_never_moves_another_convention() -> None:
    drawn = draw_documents(
        GeneratorConfigV22(seed=2, n_units=1, handbook=HandbookKnobs(trains_per_area=1)), 4
    )
    fixed_knobs = HandbookKnobs(trains_per_area=1, document_untagged=(True,) * 4)
    fixed = draw_documents(GeneratorConfigV22(seed=2, n_units=1, handbook=fixed_knobs), 4)
    assert [d.conventions for d in drawn] == [d.conventions for d in fixed]
    assert [d.pv_without_bypass for d in drawn] == [d.pv_without_bypass for d in fixed]


def test_an_allocation_shorter_than_the_documents_raises() -> None:
    knobs = HandbookKnobs(trains_per_area=1, document_untagged=(True,))
    with pytest.raises(ValueError, match="one flag per document"):
        draw_documents(GeneratorConfigV22(seed=2, n_units=1, handbook=knobs), 3)


def test_the_conventions_are_drawn_in_both_alternatives_across_documents() -> None:
    config = GeneratorConfigV22(seed=4, n_units=1, handbook=HandbookKnobs(trains_per_area=1))
    documents = draw_documents(config, 60)
    assert {d.conventions.on_off_letter.value for d in documents} == {"X", "Y"}
    assert {d.conventions.spare_naming for d in documents} == set(SpareNaming)
    assert {d.pv_without_bypass for d in documents} == {True, False}


# ---- untagged manual valves ----------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_an_untagged_document_prints_no_tag_on_a_manual_valve_and_every_other_valve_one(
    seed: int,
) -> None:
    view = _view(seed, 10, (True,))
    manual = set(_manual_valves(view))
    assert manual
    for node, data in view.graph.nodes(data=True):
        if data["node_class"] in VALVE_CLASSES:
            assert bool(data.get("tag")) == (node not in manual), node
    assert _run("TOG113-MANUAL-VALVE-TAGS", view).violations == ()


@pytest.mark.parametrize("seed", SEEDS)
def test_a_tagged_document_tags_every_manual_valve(seed: int) -> None:
    view = _view(seed, 10, (False,))
    assert all(view.graph.nodes[n].get("tag") for n in _manual_valves(view))
    result = _run("TOG113-MANUAL-VALVE-TAGS", view)
    assert result.violations == () and result.checked > 0


def test_manual_valves_follow_their_own_documents_convention() -> None:
    view = _view(2, 2, (True, False, True, False, True, False, True, False))
    flags = {d.document_no: d.manual_valves_untagged for d in view.documents}
    assert len(flags) > 1
    for valve in _manual_valves(view):
        assert (not view.graph.nodes[valve].get("tag")) == flags[document_of_node(view, valve)]
    assert _run("TOG113-MANUAL-VALVE-TAGS", view).violations == ()


@pytest.mark.parametrize("untagged", [True, False])
def test_network_root_valves_follow_their_areas_document(untagged: bool) -> None:
    view = _view(1, 2, (untagged,) * 8)
    roots = [n for n, role in view.roles.items() if role == "network_root_block"]
    assert roots
    assert all(bool(view.graph.nodes[n].get("tag")) is not untagged for n in roots)


def test_a_control_valve_does_not_depend_on_the_manual_tags() -> None:
    untagged, tagged = _view(1, 10, (True,)), _view(1, 10, (False,))

    def control(view: RuleView) -> set[str]:
        return {n for n in view.graph.nodes if is_control_valve(view.graph, n)}

    assert control(untagged) == control(tagged) and control(tagged)


def test_tog113_catches_a_tag_on_a_manual_valve_of_an_untagged_document() -> None:
    view = _view(1, 10, (True,))
    valve = _manual_valves(view)[0]
    graph = view.graph.copy()
    graph.nodes[valve]["tag"] = "GTV-1999"
    result = _run("TOG113-MANUAL-VALVE-TAGS", replace(view, graph=graph))
    assert [v.node_id for v in result.violations] == [valve]


def test_tog113_catches_a_missing_tag_on_a_control_valve_and_on_a_safety_device() -> None:
    view = _view(1, 10, (True,))
    graph = view.graph.copy()
    automatic = [n for n in graph if is_control_valve(graph, n)][:1]
    safety = [n for n, d in graph.nodes(data=True) if "SafetyValve" in d["node_class"]][:1]
    assert automatic and safety
    for node in (*automatic, *safety):
        del graph.nodes[node]["tag"]
    result = _run("TOG113-MANUAL-VALVE-TAGS", replace(view, graph=graph))
    assert {v.node_id for v in result.violations} == {*automatic, *safety}


def test_tog113_is_not_applicable_to_a_v21_plant() -> None:
    view = plant_view(1, units_for_30_sheets(1))
    assert _run("TOG113-MANUAL-VALVE-TAGS", view) == CheckResult(checked=0)


# ---- one convention per document -----------------------------------------------------------------


def test_every_train_of_a_document_keeps_the_documents_conventions() -> None:
    view = _view(3, 2)
    per = {d.document_no: d.conventions for d in view.documents}
    assert len(per) > 1
    for train in view.plan.trains:
        assert train.conventions == per[document_of_train(train.train_no, 2)]
    assert check_document_conventions(view) == len(view.plan.trains)
    assert _run("TOG28-SPARE-NAMING", view).violations == ()


def test_tog28_catches_a_train_that_leaves_its_documents_convention() -> None:
    view = _view(3, 2)
    document = view.documents[0]
    suffix = document.conventions.spare_naming is SpareNaming.SUFFIX
    other = SpareNaming.CONSECUTIVE if suffix else SpareNaming.SUFFIX
    trains = list(view.plan.trains)
    changed = document.conventions.model_copy(update={"spare_naming": other})
    trains[0] = trains[0].model_copy(update={"conventions": changed})
    plan = view.plan.model_copy(update={"trains": tuple(trains)})
    broken = replace(view, generated=replace(view.generated, plan=plan))
    assert _run("TOG28-SPARE-NAMING", broken).violations
