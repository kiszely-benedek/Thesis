"""Invariants S21, S23 and S24 over a whole v2 plant: motors, train conventions, the class list.

Not a test module (no `test_` prefix). Same shape as `plant_invariants.py`, which holds the
`PlantView` these checks read: each `check_*` raises `AssertionError` naming the offender and
returns how many things it checked.
"""

from __future__ import annotations

from plant_invariants import PlantView
from pydantic import BaseModel

from plantgraph.adapters.pydexpi_builder_v2_equipment import motor_tag
from plantgraph.benchmark.v2.coverage import GENERATED_CLASSES
from plantgraph.benchmark.v2.symbols import plan_node_classes
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.vocabulary import ItemKind, SpareNaming, item_kind
from plantgraph.graph import schema

# ---- S21, S23, S24 -------------------------------------------------------------------------------


def check_s21(view: PlantView) -> int:
    """S21: a motor-driven machine has exactly one motor, sub-tagged with the machine's number."""
    machines = {m.id: m for m in view.model.conceptualModel.taggedPlantItems}  # type: ignore[union-attr]
    checked = 0
    for unit in view.generated.plan.units:
        for spec in unit.instance.plan.equipment:
            motors = machines[spec.node_id].motors  # type: ignore[attr-defined]
            if not spec.has_motor:
                assert motors == [], f"{spec.tag} has a motor but is not motor-driven"
                continue
            assert [m.subTagName for m in motors] == [motor_tag(spec.tag)], spec.tag
            checked += 1
    return checked


def check_s23(view: PlantView) -> int:
    """S23: within a train the on-off letter and the spare naming do not change (read from tags)."""
    plan, checked = view.generated.plan, 0
    for train in plan.trains:
        units = [u for u in plan.units if u.slot.train_no == train.train_no]
        letters = _on_off_letters(view, [u.slot.unit_no for u in units])
        assert letters <= {train.conventions.on_off_valve_letters}, (train.train_no, letters)
        for unit in units:
            for members in unit.instance.plan.spare_sets:
                _check_spare_tags(
                    unit.instance.plan.equipment, members, train.conventions.spare_naming
                )
                checked += 1
    return checked


def _on_off_letters(view: PlantView, unit_nos: list[int]) -> set[str]:
    letters: set[str] = set()
    for _, data in view.graph.nodes(data=True):
        parsed = parse_tag(data.get("tag") or "")
        in_train = data.get("unit_id") in {str(n) for n in unit_nos}
        if (
            parsed
            and in_train
            and item_kind(data["node_class"], parsed.letters) is ItemKind.ON_OFF_VALVE
        ):
            letters.add(parsed.letters)
    return letters


def _check_spare_tags(
    equipment: tuple[object, ...], members: tuple[str, ...], naming: SpareNaming
) -> None:
    tags = [parse_tag(e.tag) for e in equipment if e.node_id in members]  # type: ignore[attr-defined]
    assert all(tags), members
    numbers = [t.sequence for t in tags if t]
    suffixes = [t.train for t in tags if t]
    if naming is SpareNaming.SUFFIX:
        assert len(set(numbers)) == 1 and suffixes == list("ABC"[: len(members)]), (
            members,
            suffixes,
        )
    else:
        assert suffixes == [None] * len(members), members
        assert numbers == list(range(numbers[0], numbers[0] + len(members))), numbers


def check_s24(view: PlantView) -> int:
    """S24: only the 77 generated classes, no `Custom*` in the DEXPI model, two parent classes."""
    used: set[str] = set()
    for unit in view.generated.plan.units:
        used |= set(plan_node_classes(unit.instance.plan).values())
    assert used <= GENERATED_CLASSES, f"classes outside the 77: {sorted(used - GENERATED_CLASSES)}"
    parents = {c for c in used if not schema.CLASS_SPECS[schema.NodeClass(c)].leaf}
    assert parents <= {"CheckValve", "ProcessInstrumentationFunction"}, sorted(parents)
    custom = sorted({name for name in _class_names(view.model) if name.startswith("Custom")})
    assert not custom, f"Custom classes in the DEXPI model: {custom}"
    return len(used)


def _class_names(root: object) -> set[str]:
    """The class name of every pydantic object reachable from `root` (each visited once)."""
    names: set[str] = set()
    seen: set[int] = set()
    stack = [root]
    while stack:
        item = stack.pop()
        if isinstance(item, BaseModel):
            if id(item) in seen:  # the model is a graph: a nozzle points back at its machine
                continue
            seen.add(id(item))
            names.add(type(item).__name__)
            stack.extend(getattr(item, field) for field in type(item).model_fields)
        elif isinstance(item, list | tuple):
            stack.extend(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
    return names
