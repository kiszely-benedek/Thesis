"""Load-plan profiles: `occurrence` is unchanged, `plant` and `both` add the merged layer.

Expected counts are tallied from the sheets and the resolution here, never
from the plan's own rows.
"""

from __future__ import annotations

import hashlib
from collections import Counter

import pytest

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.resolution.models import Resolution
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan
from store_toy_corpus import toy_corpus

_CORPUS = "acme-plant-01"

#: sha256 of today's `occurrence` plan JSON (without the new `profile` field), taken from the
#: code as it stood before the plant layer existed (commit eba87c0), generated plants seed 7.
#: Re-recorded for ADR-0044 (control-valve tags changed; plan structure did not).
_GOLDEN_OCCURRENCE_PLAN_HASH = {
    0.0: "57a9d7c2717ac3c6157aaa1272eb3beb7c249a60012bb4ced95a52e87cd0c830",
    0.5: "f329fd7615463fc5d9da71630fdea4234839604ab4b610683faf16b94f9766c6",
}


def _plan(
    duplication_rate: float, profile: str = "occurrence"
) -> tuple[LoadPlan, Resolution, list[SheetGraph]]:
    sheets, resolution = toy_corpus(duplication_rate)
    plan = build_load_plan(_CORPUS, sheets, resolution, profile=profile)  # type: ignore[arg-type]
    return plan, resolution, sheets


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_the_occurrence_plan_is_byte_identical_to_the_one_before_the_plant_layer(
    duplication_rate: float,
) -> None:
    plan, _resolution, _sheets = _plan(duplication_rate)
    digest = hashlib.sha256(plan.model_dump_json(exclude={"profile"}).encode()).hexdigest()
    assert digest == _GOLDEN_OCCURRENCE_PLAN_HASH[duplication_rate]


def test_the_default_profile_is_occurrence() -> None:
    sheets, resolution = toy_corpus(0.5)
    default = build_load_plan(_CORPUS, sheets, resolution)
    assert default.profile == "occurrence"
    assert default == build_load_plan(_CORPUS, sheets, resolution, profile="occurrence")


# --- independent tallies ---------------------------------------------------------------------


def _paired_keys(resolution: Resolution) -> set[str]:
    pairs = resolution.connector_pairs
    return {p.from_key for p in pairs} | {p.to_key for p in pairs}


def _item_tallies(
    sheets: list[SheetGraph], resolution: Resolution
) -> tuple[Counter[str], Counter[str]]:
    """Labels and relationship types of the item layer alone (no sheets, units or plants)."""
    labels: Counter[str] = Counter()
    for _key, attrs in resolution.plant.nodes(data=True):
        chain = schema.labels_for(attrs["node_class"])
        labels.update(["CorpusNode", schema.PLANT_ITEM_LABEL, *chain])
        if attrs["node_class"] in schema.CONNECTOR_CLASSES:
            labels[schema.UNRESOLVED_CONNECTOR_LABEL] += 1

    home_of = {r: g.home for g in resolution.identity_groups for r in g.references}
    paired = _paired_keys(resolution)
    sheets_of_item: dict[str, set[str]] = {}
    drawn_as = 0
    for sheet in sheets:
        for node_id in sheet.graph.nodes:
            key = f"{sheet.sheet_id}:{node_id}"
            if key not in paired:
                sheets_of_item.setdefault(home_of.get(key, key), set()).add(sheet.sheet_id)
                drawn_as += 1

    types = Counter(attrs["relation"] for _s, _t, attrs in resolution.plant.edges(data=True))
    types[schema.Relation.IS_DRAWN_ON.value] = sum(len(s) for s in sheets_of_item.values())
    types[schema.Relation.IS_LOCATED_IN.value] = sum(
        1 for _k, attrs in resolution.plant.nodes(data=True) if "unit_id" in attrs
    )
    types[schema.Relation.DRAWN_AS.value] = drawn_as
    return labels, types


def _item_units_and_plants(resolution: Resolution) -> tuple[set[str], set[str]]:
    nodes = [attrs for _k, attrs in resolution.plant.nodes(data=True)]
    return (
        {a["unit_id"] for a in nodes if "unit_id" in a},
        {a["plant_id"] for a in nodes if "plant_id" in a},
    )


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_plant_profile_counts_equal_an_independent_tally(duplication_rate: float) -> None:
    plan, resolution, sheets = _plan(duplication_rate, "plant")
    labels, types = _item_tallies(sheets, resolution)
    units, plants = _item_units_and_plants(resolution)
    structure = Counter(
        {
            "DrawingSet": 1,
            "Sheet": len(sheets),
            "PlantSection": len(units),
            "ProcessPlant": len(plants),
        }
    )
    structure["CorpusNode"] = sum(structure.values())
    types[schema.Relation.HAS_SHEET.value] = len(sheets)
    types[schema.Relation.IS_LOCATED_IN.value] += len(units)  # each unit sits in one plant
    del types[schema.Relation.DRAWN_AS.value]

    assert plan.profile == "plant"
    assert plan.expected_node_labels == dict(labels + structure)
    assert plan.expected_relationship_types == dict(types)


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_both_profile_counts_equal_occurrence_plus_the_item_layer(duplication_rate: float) -> None:
    both, resolution, sheets = _plan(duplication_rate, "both")
    occurrence, _r, _s = _plan(duplication_rate, "occurrence")
    labels, types = _item_tallies(sheets, resolution)

    assert both.profile == "both"
    assert both.expected_node_labels == dict(Counter(occurrence.expected_node_labels) + labels)
    assert both.expected_relationship_types == dict(
        Counter(occurrence.expected_relationship_types) + types
    )


def test_only_the_both_profile_has_drawn_as() -> None:
    drawn_as = schema.Relation.DRAWN_AS.value
    assert drawn_as not in _plan(0.5, "occurrence")[0].expected_relationship_types
    assert drawn_as not in _plan(0.5, "plant")[0].expected_relationship_types
    assert _plan(0.5, "both")[0].expected_relationship_types[drawn_as] > 0


# --- what the statements actually carry ------------------------------------------------------


def _node_rows(plan: LoadPlan) -> list[tuple[tuple[str, ...], str]]:
    found = []
    for statement in plan.node_statements:
        inside = statement.query.split("(n:", 1)[1].split(")", 1)[0]
        for row in statement.parameters["rows"]:  # type: ignore[attr-defined]
            found.append((tuple(inside.split(":")), row["props"]["uid"]))
    return found


def _label_whitelist() -> set[str]:
    chains = {label for spec in schema.CLASS_SPECS.values() for label in spec.labels}
    return chains | {"CorpusNode", schema.PLANT_ITEM_LABEL, schema.UNRESOLVED_CONNECTOR_LABEL}


@pytest.mark.parametrize("profile", ["occurrence", "plant", "both"])
def test_every_label_is_on_the_whitelist_and_every_uid_is_unique(profile: str) -> None:
    plan, _resolution, _sheets = _plan(0.5, profile)
    rows = _node_rows(plan)

    assert {label for labels, _uid in rows for label in labels} <= _label_whitelist()
    uids = [row_uid for _labels, row_uid in rows]
    assert len(uids) == len(set(uids))


def test_item_uids_never_collide_with_occurrence_uids_in_both() -> None:
    plan, resolution, _sheets = _plan(0.5, "both")
    uids = {row_uid for _labels, row_uid in _node_rows(plan)}
    assert all(f"{_CORPUS}|item:{key}" in uids for key in resolution.plant)
    assert all(f"{_CORPUS}|{key}" in uids for key in resolution.plant)  # homes, as occurrences


def test_plant_profile_derives_the_same_units_as_the_occurrence_layer() -> None:
    def sections(plan: LoadPlan) -> set[str]:
        return {uid for labels, uid in _node_rows(plan) if "PlantSection" in labels}

    assert sections(_plan(0.5, "plant")[0]) == sections(_plan(0.5, "occurrence")[0])


def test_the_plant_profile_writes_no_occurrence_rows() -> None:
    plan, _resolution, _sheets = _plan(0.5, "plant")
    for labels, row_uid in _node_rows(plan):
        if "Sheet" in labels or "DrawingSet" in labels or "PlantSection" in labels:
            continue
        assert "PlantItem" in labels or "ProcessPlant" in labels, (labels, row_uid)
