"""How a B corpus gets its valve positions: the ingest step, the plan patch and the gate G0-B.

A B corpus is the same plant as its A corpus, plus one valve property, `operating_position`
(design `v2t-b` §2, §10 R4-R5). Three steps put it there:

1. **Ingest.** Generate the plant once more, read each valve's position back out of the DEXPI model
   (`positions.py`) and write `operating_positions.json` (`ingest_positions`).
2. **Patch.** The frozen `build_load_plan` rejects the property, so the plan is built as for an
   A corpus and then copied with the position added to each valve's row (`with_positions`). The
   expected label and relationship counts do not change, so the frozen loader accepts it.
3. **Gate G0-B.** The file must equal the generator plan's positions node for node, the patched
   plan must carry exactly that many, and every keyed node must be a valve (`check_g0b`).

This module reads the occurrence map, which is gold. No strategy-facing module may import it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.graph.schema import VALVE_CLASSES
from plantgraph.qa.v2tb.positions import (
    POSITIONS_FILE_NAME,
    read_operating_positions,
    write_positions_file,
)
from plantgraph.qa.v2tb.visible import OPERATING_POSITION
from plantgraph.resolution.localize import OccurrenceMap
from plantgraph.store.neo4j_plan import LoadPlan
from plantgraph.store.neo4j_rows import uid
from plantgraph.store.plant_rows import item_uid

_MAX_EXAMPLES = 5


@dataclass(frozen=True)
class PositionsRecord:
    """What the ingest step leaves behind: the positions as read, and the file's fingerprint."""

    positions: dict[str, str]
    sha256: str
    path: Path


def ingest_positions(config: GeneratorConfigV2, corpus_dir: Path) -> PositionsRecord:
    """Generate the plant once more, read the positions from DEXPI and write the file.

    The positions read from the DEXPI model must equal the generator plan's, node for node: that
    is check 1 of G0-B, made here because both are at hand.

    Raises:
        ValueError: the DEXPI reading and the plan disagree.
    """
    generated = generate_plant_v2(config)
    read = read_operating_positions(generated.model)
    planned: dict[str, str] = dict(positions_of(generated.plan.unit_plans))
    problems = _differences(read, planned)
    if problems:
        raise ValueError(f"expected the DEXPI positions to equal the plan's: {problems}")
    path = corpus_dir / POSITIONS_FILE_NAME
    return PositionsRecord(positions=read, sha256=write_positions_file(path, read), path=path)


# ---- the map and the plan patch -----------------------------------------------------------------


def positions_by_local_key(
    positions: Mapping[str, str], occurrence_map: OccurrenceMap
) -> dict[str, str]:
    """Valve node id -> code, re-keyed by the valve's opaque local key.

    Every valve has exactly one occurrence (ADR-0028 duplicates only equipment), so the map is
    one to one.

    Raises:
        ValueError: a positioned node has no occurrence, or more than one.
    """
    local_keys_of: dict[str, list[str]] = defaultdict(list)
    for local_key in occurrence_map.local_to_original:
        local_keys_of[occurrence_map.original_node_id(local_key)].append(local_key)
    by_local_key: dict[str, str] = {}
    for node_id, code in positions.items():
        keys = local_keys_of.get(node_id, [])
        if len(keys) != 1:
            raise ValueError(f"expected one occurrence of valve {node_id!r}, found {sorted(keys)}")
        by_local_key[keys[0]] = code
    return by_local_key


def with_positions(plan: LoadPlan, by_local_key: Mapping[str, str]) -> LoadPlan:
    """A copy of `plan` whose valve rows carry `operating_position`; the counts do not change.

    A row is found by its `uid`: `uid(corpus, key)` in the occurrence layer and `item_uid(corpus,
    key)` in the plant layers, so every store profile is patched. An empty map gives an equal plan.

    Raises:
        ValueError: a key has no row in any layer of the plan.
    """
    patched = plan.model_copy(deep=True)
    wanted: dict[str, tuple[str, str]] = {}
    for local_key, code in by_local_key.items():
        wanted[uid(plan.corpus_id, local_key)] = (local_key, code)
        wanted[item_uid(plan.corpus_id, local_key)] = (local_key, code)
    seen: set[str] = set()
    for props in _node_props(patched):
        hit = wanted.get(str(props.get("uid")))
        if hit is not None:
            props[OPERATING_POSITION] = hit[1]
            seen.add(hit[0])
    missing = sorted(set(by_local_key) - seen)
    if missing:
        raise ValueError(f"expected a node row for every positioned valve, none for {missing[:5]}")
    return patched


def _node_props(plan: LoadPlan) -> list[dict[str, object]]:
    """The property dict of every node row of the plan (the dicts themselves, to patch in place)."""
    found: list[dict[str, object]] = []
    for statement in plan.node_statements:
        rows = statement.parameters.get("rows")
        if not isinstance(rows, list):
            raise ValueError(f"expected a node statement with a list of rows, found {rows!r:.80}")
        found.extend(row["props"] for row in rows)
    return found


def count_positioned_rows(plan: LoadPlan) -> int:
    """How many node rows of the plan carry `operating_position`."""
    return sum(OPERATING_POSITION in props for props in _node_props(plan))


# ---- gate G0-B ----------------------------------------------------------------------------------


def valve_ids_of(plant: nx.DiGraph[str]) -> frozenset[str]:
    """The nodes of the gold plant whose class is a valve class."""
    return frozenset(n for n, data in plant.nodes(data=True) if data["node_class"] in VALVE_CLASSES)


def check_g0b(
    *,
    file_positions: Mapping[str, str],
    planned_positions: Mapping[str, str],
    valve_ids: Collection[str],
    patched_plan: LoadPlan,
) -> list[str]:
    """The problems G0-B finds (empty list = pass); it never raises.

    Args:
        file_positions: the positions file's content (read from DEXPI at ingest).
        planned_positions: `positions_of(plan.unit_plans)`, the generator plan's own answer.
        valve_ids: every valve node of the gold plant.
        patched_plan: the load plan after `with_positions`.
    """
    problems = _differences(file_positions, planned_positions)
    layers = 2 if patched_plan.profile == "both" else 1  # `both` stores each valve twice
    expected_rows = len(file_positions) * layers
    found_rows = count_positioned_rows(patched_plan)
    if found_rows != expected_rows:
        problems.append(f"patched plan has {found_rows} positioned rows, expected {expected_rows}")
    not_valves = sorted(set(file_positions) - set(valve_ids))
    if not_valves:
        problems.append(f"positions keyed on non-valves: {not_valves[:_MAX_EXAMPLES]}")
    return problems


def _differences(file_positions: Mapping[str, str], planned: Mapping[str, str]) -> list[str]:
    """Node-for-node comparison of two position maps, as readable problem lines."""
    problems: list[str] = []
    missing = sorted(set(planned) - set(file_positions))
    extra = sorted(set(file_positions) - set(planned))
    changed = sorted(
        n for n in set(planned) & set(file_positions) if planned[n] != file_positions[n]
    )
    if missing:
        problems.append(
            f"{len(missing)} planned valves have no position: {missing[:_MAX_EXAMPLES]}"
        )
    if extra:
        problems.append(f"{len(extra)} positions the plan does not have: {extra[:_MAX_EXAMPLES]}")
    if changed:
        problems.append(f"{len(changed)} positions differ from the plan: {changed[:_MAX_EXAMPLES]}")
    return problems
