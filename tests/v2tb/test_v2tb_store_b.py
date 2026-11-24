"""R5 and G0-B: the positions map, the plan patch and the ingest gate (design `v2t-b` §10)."""

from __future__ import annotations

import pytest
from plants_b import real_corpus
from seed1_b import seed1

from plantgraph.qa.v2tb.store_b import (
    check_g0b,
    count_positioned_rows,
    positions_by_local_key,
    valve_ids_of,
    with_positions,
)
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.resolution.localize import OccurrenceMap
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.neo4j_rows import uid
from plantgraph.store.plant_rows import StoreProfile, item_uid

_PROFILES: list[StoreProfile] = ["occurrence", "plant", "plant_lines", "both"]


def _valve_keys(n: int) -> dict[str, str]:
    """Local key -> code for the first `n` valves of the small plant (real keys, one code each)."""
    corpus = real_corpus()
    keys = [
        f"{sheet.sheet_id}:{node}"
        for sheet in corpus.localized_sheets
        for node, attrs in sheet.graph.nodes(data=True)
        if "Valve" in attrs["node_class"]
    ]
    return {key: "NC" for key in sorted(keys)[:n]}


# ---- the map -----------------------------------------------------------------------------------


def test_the_map_rekeys_each_valve_by_its_one_local_key() -> None:
    occurrences = OccurrenceMap(local_to_original={"S1:a": "S1:v1", "S2:b": "S2:v2"})

    assert positions_by_local_key({"v1": "NO", "v2": "NC"}, occurrences) == {
        "S1:a": "NO",
        "S2:b": "NC",
    }


def test_the_map_refuses_a_valve_with_no_occurrence_or_with_two() -> None:
    occurrences = OccurrenceMap(
        local_to_original={"S1:a": "S1:v1", "S2:b": "S2:v2", "S3:c": "S3:v2"}
    )

    with pytest.raises(ValueError, match="one occurrence of valve 'v9'"):
        positions_by_local_key({"v9": "NO"}, occurrences)
    with pytest.raises(ValueError, match="one occurrence of valve 'v2'"):
        positions_by_local_key({"v2": "NO"}, occurrences)


# ---- the plan patch ----------------------------------------------------------------------------


@pytest.mark.parametrize("profile", _PROFILES)
def test_a_patched_plan_carries_the_code_on_every_row_of_a_positioned_valve(
    profile: StoreProfile,
) -> None:
    corpus = real_corpus()
    plan = build_load_plan("c", corpus.localized_sheets, corpus.resolution, profile=profile)
    by_key = _valve_keys(5)

    patched = with_positions(plan, by_key)

    layers = 2 if profile == "both" else 1
    assert count_positioned_rows(patched) == len(by_key) * layers
    assert count_positioned_rows(plan) == 0  # a new plan: the original is untouched
    assert patched.expected_node_labels == plan.expected_node_labels
    assert patched.expected_relationship_types == plan.expected_relationship_types
    wanted = {uid("c", k) for k in by_key} | {item_uid("c", k) for k in by_key}
    rows = [
        row["props"]
        for statement in patched.node_statements
        for row in statement.parameters["rows"]  # type: ignore[attr-defined]
    ]
    positioned = {row["uid"] for row in rows if OPERATING_POSITION in row}
    assert positioned <= wanted
    assert {row[OPERATING_POSITION] for row in rows if OPERATING_POSITION in row} == {"NC"}


def test_an_empty_map_gives_an_equal_plan_and_a_key_with_no_row_raises() -> None:
    corpus = real_corpus()
    plan = build_load_plan("c", corpus.localized_sheets, corpus.resolution, profile="plant")

    assert with_positions(plan, {}).model_dump() == plan.model_dump()
    with pytest.raises(ValueError, match="node row for every positioned valve"):
        with_positions(plan, {"S9:nope": "NO"})


# ---- gate G0-B ---------------------------------------------------------------------------------


def _gate(file_positions: dict[str, str]) -> list[str]:
    plant = seed1()
    return check_g0b(
        file_positions=file_positions,
        planned_positions=plant.planned,
        valve_ids=valve_ids_of(plant.corpus.plant),
        patched_plan=plant.patched_plan,
    )


def test_g0b_passes_on_forced_untagged_seed_1_with_the_positions_read_from_dexpi() -> None:
    plant = seed1()

    assert len(plant.from_dexpi) == 1493  # the ruling's count (design §10.8 table)
    assert _gate(plant.from_dexpi) == []


def test_g0b_fails_on_one_deleted_entry() -> None:
    positions = dict(seed1().from_dexpi)
    del positions[sorted(positions)[0]]

    problems = _gate(positions)

    assert any("have no position" in p for p in problems)
    assert any("positioned rows" in p for p in problems)  # the plan holds one more than the file


def test_g0b_fails_on_one_altered_entry() -> None:
    positions = dict(seed1().from_dexpi)
    node = sorted(positions)[0]
    positions[node] = "NC" if positions[node] != "NC" else "NO"

    problems = _gate(positions)

    assert problems == [f"1 positions differ from the plan: ['{node}']"]


def test_g0b_fails_on_a_position_keyed_on_a_non_valve() -> None:
    plant = seed1()
    positions = dict(plant.from_dexpi)
    tank = next(n for n in plant.corpus.plant.nodes if n not in valve_ids_of(plant.corpus.plant))
    positions[tank] = "NO"

    problems = _gate(positions)

    assert any("non-valves" in p for p in problems)
