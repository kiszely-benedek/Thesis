"""Plans the synthetic plant graph's topology (`plant-generator.md` §3.3).

This module **decides the topology only**: which equipment goes into which
unit, which two pieces are joined by a pipe segment, where a valve sits on it,
which valve controls which piece of equipment. Building the actual graph or
DEXPI model is done by a `PlantBuilder` (`generator_models.py`) — this module
only passes it strings, integers, and floats, and never imports pyDEXPI
(`plant-generator.md`, "Offline split of step 3": the pyDEXPI package cannot be
installed on this machine, so topology planning and DEXPI construction split
into two separate steps).

`plan_plant` is the single entry point. Every random decision goes through a
`random.Random(config.seed)` — never the global `random` module, and never an
iteration over a `set` — so the same seed always produces the same graph
(`plant-generator.md` invariants 3, 4).
"""

from __future__ import annotations

import random

from plantgraph.benchmark.generator_models import (
    GenerationRecord,
    GeneratorConfig,
    LoopSpec,
    PlantBuilder,
    StreamKind,
    ValveSpec,
)
from plantgraph.graph.schema import CLASS_SPECS, OPERATED_VALVE_CLASSES, VALVE_CLASSES, NodeClass


def plan_plant(config: GeneratorConfig, builder: PlantBuilder) -> GenerationRecord:
    """Plan a plant's topology per `config`, and have `builder` construct it.

    The order of the five steps is itself the specification
    (`plant-generator.md` §3.3): units, equipment, intra-unit streams,
    inter-unit streams, control loops.
    """
    state = _GenerationState(config, builder)
    state.add_sections()
    state.add_equipment()
    state.add_intra_unit_streams()
    state.add_inter_unit_streams()
    state.add_control_loops()
    return state.record()


class _GenerationState:
    """`plan_plant`'s internal, non-public state: counters and intermediate results.

    A class so that the five steps (§3.3) live in named methods sharing common
    state, instead of one long function.
    """

    def __init__(self, config: GeneratorConfig, builder: PlantBuilder) -> None:
        self.config = config
        self.builder = builder
        self.rng = random.Random(config.seed)

        #: line_number -> where that pipe segment originated (the GenerationRecord's material)
        self.stream_kind: dict[str, StreamKind] = {}
        #: units_equipment[unit index] = the unit's equipment node_ids, in insertion order
        self.units_equipment: list[list[str]] = []
        #: any equipment node_id added so far -> its unit's number (1-based) —
        #: valves and control loops use this to know which unit they belong to
        self.node_unit: dict[str, int] = {}
        #: pipe segments added so far, as ordered (source, target) pairs —
        #: the duplicate and recycle checks build on this
        self.stream_pairs: set[tuple[str, str]] = set()
        #: equipment node_id -> the valves on its outgoing pipe segments, in insertion order
        #: (only these are eligible as control-loop candidates, §3.3 step 5)
        self.valves_by_source: dict[str, list[ValveSpec]] = {}
        #: node_ids of valves already under control — at most one loop per valve
        self.controlled_valves: set[str] = set()

        self._node_seq: dict[tuple[int, str], int] = {}
        self._tag_seq: dict[tuple[int, str], int] = {}
        self._loop_no: dict[int, int] = {}
        self._stream_seq = 0

    # ---- step 0: units --------------------------------------------------------------

    def add_sections(self) -> None:
        """Create every process unit before adding anything else into them."""
        for unit_index in range(self.config.n_units):
            self.builder.add_section(unit_no=unit_index + 1)

    # ---- step 1: equipment ------------------------------------------------------------

    def add_equipment(self) -> None:
        """Add a uniformly-distributed count of weighted-random equipment into every unit."""
        weighted_classes = sorted(self.config.equipment_weights)
        weights = [self.config.equipment_weights[name] for name in weighted_classes]
        for unit_index in range(self.config.n_units):
            unit_no = unit_index + 1
            count = self.rng.randint(
                self.config.equipment_per_unit_min, self.config.equipment_per_unit_max
            )
            equipment_ids: list[str] = []
            for _ in range(count):
                equipment_ids.append(self._add_one_equipment(unit_no, weighted_classes, weights))
            self.units_equipment.append(equipment_ids)

    def _add_one_equipment(
        self, unit_no: int, weighted_classes: list[str], weights: list[float]
    ) -> str:
        """Add one piece of equipment: pick a class, mint an id/tag, submit it to the builder."""
        node_class = self.rng.choices(weighted_classes, weights)[0]
        node_id = self._next_node_id(unit_no, "eq")
        tag, tag_prefix, tag_seq = self._next_tag(unit_no, node_class)
        self.builder.add_equipment(
            node_id=node_id,
            node_class=node_class,
            unit_no=unit_no,
            tag=tag,
            tag_prefix=tag_prefix,
            tag_seq=tag_seq,
        )
        self.node_unit[node_id] = unit_no
        return node_id

    # ---- step 2: intra-unit streams (random tree + recycle) -------------------------

    def add_intra_unit_streams(self) -> None:
        """Build a random tree within each unit, then add a recycle stream with some probability."""
        for equipment_ids in self.units_equipment:
            tree_parent = self._add_tree(equipment_ids)
            self._maybe_add_recycle(equipment_ids, tree_parent)

    def _add_tree(self, equipment_ids: list[str]) -> dict[int, int]:
        """A random recursive tree: every node's parent is an earlier, randomly chosen node."""
        tree_parent: dict[int, int] = {}
        for child_index in range(1, len(equipment_ids)):
            parent_index = self.rng.randrange(child_index)
            tree_parent[child_index] = parent_index
            self._add_stream(
                equipment_ids[parent_index], equipment_ids[child_index], StreamKind.TREE
            )
        return tree_parent

    def _maybe_add_recycle(self, equipment_ids: list[str], tree_parent: dict[int, int]) -> None:
        """With some probability, add a backward-pointing (recycle) stream within the unit."""
        if self.rng.random() >= self.config.p_recycle:
            return
        candidates = self._recycle_candidates(equipment_ids, tree_parent)
        if not candidates:
            return
        src_id, dst_id = self.rng.choice(candidates)
        self._add_stream(src_id, dst_id, StreamKind.RECYCLE)

    def _recycle_candidates(
        self, equipment_ids: list[str], tree_parent: dict[int, int]
    ) -> list[tuple[str, str]]:
        """The possible recycle pairs: an earlier, non-parent equipment with no stream yet."""
        candidates: list[tuple[str, str]] = []
        for src_index in range(len(equipment_ids)):
            for dst_index in range(1, src_index):
                if tree_parent.get(src_index) == dst_index:
                    continue
                src_id, dst_id = equipment_ids[src_index], equipment_ids[dst_index]
                if not self._has_stream(src_id, dst_id):
                    candidates.append((src_id, dst_id))
        return candidates

    def _has_stream(self, a: str, b: str) -> bool:
        """True if a pipe segment already runs between a and b, in either direction."""
        return (a, b) in self.stream_pairs or (b, a) in self.stream_pairs

    # ---- step 3: inter-unit streams (mandatory + optional cross-link) ----------------

    def add_inter_unit_streams(self) -> None:
        """Join every unit (except the first) to an earlier one, with an optional cross-link."""
        for unit_index in range(1, self.config.n_units):
            self._add_cross_unit_stream(unit_index)
            self._maybe_add_cross_link(unit_index)

    def _add_cross_unit_stream(self, unit_index: int) -> None:
        """The mandatory stream: from equipment in an earlier unit, to this unit's first."""
        upstream_index = self.rng.randrange(unit_index)
        src_id = self.rng.choice(self.units_equipment[upstream_index])
        dst_id = self.units_equipment[unit_index][0]
        self._add_stream(src_id, dst_id, StreamKind.CROSS_UNIT)

    def _maybe_add_cross_link(self, unit_index: int) -> None:
        """With some probability, add an extra stream from an earlier unit to a non-first piece."""
        equipment_ids = self.units_equipment[unit_index]
        # rng.random() always runs; the length check never consumes randomness —
        # this keeps the call sequence identical regardless of unit size
        if self.rng.random() >= self.config.p_cross_link or len(equipment_ids) <= 1:
            return
        source_unit_index = self.rng.randrange(unit_index)
        src_id = self.rng.choice(self.units_equipment[source_unit_index])
        dst_id = self.rng.choice(equipment_ids[1:])
        if (src_id, dst_id) not in self.stream_pairs:
            self._add_stream(src_id, dst_id, StreamKind.CROSS_LINK)

    # ---- step 4: adding one pipe segment (every stream goes through this) --------------------

    def _add_stream(self, src_id: str, dst_id: str, kind: StreamKind) -> None:
        """Add one pipe segment with its valves, and record where it originated.

        Raises:
            ValueError: if a pipe segment already exists on this ordered (source, target) pair.
        """
        if (src_id, dst_id) in self.stream_pairs:
            raise ValueError(
                f"duplicate stream {src_id} -> {dst_id}; "
                "a stream already exists on this ordered pair"
            )
        fluid_code = self.rng.choice(self.config.fluid_codes)
        self._stream_seq += 1
        line_number = f"{fluid_code}-{self._stream_seq}"
        valves = self._add_valves(src_id)

        self.builder.add_stream(
            line_number=line_number,
            fluid_code=fluid_code,
            src_id=src_id,
            dst_id=dst_id,
            valves=valves,
        )

        self.stream_pairs.add((src_id, dst_id))
        self.stream_kind[line_number] = kind
        self.valves_by_source.setdefault(src_id, []).extend(valves)

    def _add_valves(self, src_id: str) -> list[ValveSpec]:
        """Mint the valves that sit on the pipe segment, tied to the source's unit (§3.3 step 4)."""
        unit_no = self.node_unit[src_id]
        valve_count = self.rng.randint(0, self.config.valves_per_stream_max)
        valves: list[ValveSpec] = []
        for _ in range(valve_count):
            node_class = self.rng.choice(sorted(VALVE_CLASSES))
            node_id = self._next_node_id(unit_no, "va")
            tag, _, _ = self._next_tag(unit_no, node_class)
            valves.append(ValveSpec(node_id=node_id, node_class=node_class, tag=tag))
        return valves

    # ---- step 5: control loops ---------------------------------------------------------

    def add_control_loops(self) -> None:
        """For every piece of equipment, in node-id order, optionally assign a control loop."""
        all_equipment = sorted(
            equipment_id for unit in self.units_equipment for equipment_id in unit
        )
        for equipment_id in all_equipment:
            self._maybe_add_control_loop(equipment_id)

    def _maybe_add_control_loop(self, equipment_id: str) -> None:
        """With some probability, put a control loop on a not-yet-controlled, operable valve."""
        if self.rng.random() >= self.config.p_control_loop:
            return
        candidates = [
            valve
            for valve in self.valves_by_source.get(equipment_id, [])
            if valve.node_class in OPERATED_VALVE_CLASSES
            and valve.node_id not in self.controlled_valves
        ]
        if not candidates:
            return

        valve = self.rng.choice(candidates)
        variable = self.rng.choice("FLPT")
        unit_no = self.node_unit[equipment_id]
        loop = LoopSpec(
            equipment_id=equipment_id,
            valve_id=valve.node_id,
            variable=variable,
            unit_no=unit_no,
            loop_no=self._next_loop_no(unit_no),
            # the order (PSGF, PIF, AF) matters: the "in" counter increments in this order
            psgf_id=self._next_node_id(unit_no, "in"),
            pif_id=self._next_node_id(unit_no, "in"),
            af_id=self._next_node_id(unit_no, "in"),
        )
        self.builder.add_control_loop(loop)
        self.controlled_valves.add(valve.node_id)

    # ---- id and tag minting (§3.3 "Ids and tags") ----------------------------------

    def _next_node_id(self, unit_no: int, kind: str) -> str:
        """A new node id: `{plant_id}-u{unit_no}-{kind}{seq}`, `seq` per (unit, kind)."""
        key = (unit_no, kind)
        seq = self._node_seq.get(key, 0) + 1
        self._node_seq[key] = seq
        return f"{self.config.plant_id}-u{unit_no}-{kind}{seq}"

    def _next_tag(self, unit_no: int, node_class: str) -> tuple[str, str, int]:
        """An equipment/valve tag: `{prefix}-{unit_no}-{seq}`, `seq` per (unit, prefix)."""
        prefix = CLASS_SPECS[NodeClass(node_class)].tag_prefix
        if prefix is None:
            raise ValueError(f"node_class {node_class!r} has no tag_prefix in schema.CLASS_SPECS")
        key = (unit_no, prefix)
        seq = self._tag_seq.get(key, 0) + 1
        self._tag_seq[key] = seq
        return f"{prefix}-{unit_no}-{seq}", prefix, seq

    def _next_loop_no(self, unit_no: int) -> int:
        """The control-loop sequence number ("s" in §3.3), counted separately per unit."""
        loop_no = self._loop_no.get(unit_no, 0) + 1
        self._loop_no[unit_no] = loop_no
        return loop_no

    # ---- result ---------------------------------------------------------------------

    def record(self) -> GenerationRecord:
        """The completed generation's answer key: config, seed, and every stream's origin."""
        return GenerationRecord(
            plant_id=self.config.plant_id,
            seed=self.config.seed,
            generator_config=self.config.model_dump_json(),
            pydexpi_version=self.builder.backend_version,
            stream_kind=self.stream_kind,
        )
