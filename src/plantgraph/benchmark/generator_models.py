"""Data model for the synthetic plant-graph generator (`plant-generator.md` §3.2, §3.5).

The module describes two sharply separate things:

- **what the user asks for** — `GeneratorConfig`: how many units, how much
  equipment per unit, how likely a unit is to get recirculation (recycle) or a
  cross-link starting from another unit, and so on. Every field here is a
  freely tunable parameter, not a hardcoded constant (`plant-generator.md` §3.2
  — "All defaults are arbitrary and test-sized").
- **what a backend gets back from the generator's topology decisions** —
  `ValveSpec`, `LoopSpec` for the `PlantBuilder` protocol's calls, and
  `GenerationRecord` as the answer key for a completed generation run.

**Why a Protocol, and why no pyDEXPI here.** On the offline machine, the
pyDEXPI package cannot be installed (`plant-generator.md`, "Offline split of
step 3" note). The `PlantBuilder` protocol therefore only describes WHICH
calls the topology planner expects from a backend — so the real pyDEXPI
backend can implement this same protocol later, and the tests'
(`tests/graph_plant_builder.py`) can implement it right now. `build()` is
deliberately absent from the protocol: producing the final output (a DEXPI
model or a graph) is a backend-specific step, not part of topology planning.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from plantgraph.graph import schema


class StreamKind(str, Enum):
    """Where a pipe segment (`stream`, material flow between two equipment nodes) originates.

    Only enters the answer key (`GenerationRecord`) for analysis purposes — in
    the generated graph, the `stream_kind` property is **gold**, never present
    in the store under retrieval (`plant-generator.md` §4.4).
    """

    TREE = "tree"  # a random tree edge within the unit
    RECYCLE = "recycle"  # from a later piece of equipment back to an earlier one, same unit
    CROSS_UNIT = "cross_unit"  # the mandatory cross-flow that chains the units together
    CROSS_LINK = "cross_link"  # an optional extra cross-flow starting from an earlier unit


class GeneratorConfig(BaseModel):
    """Every setting for the synthetic plant-graph generator (`plant-generator.md` §3.2).

    Every default is arbitrary and test-sized; none of them make a claim about
    real plants.
    """

    plant_id: str = Field(default="plant0", pattern=r"^[a-z0-9]+$")
    seed: int = 0
    n_units: int = Field(default=4, ge=1)
    equipment_per_unit_min: int = Field(default=3, ge=1)
    equipment_per_unit_max: int = Field(default=8, ge=1)
    p_recycle: float = Field(default=0.2, ge=0.0, le=1.0)
    p_cross_link: float = Field(default=0.2, ge=0.0, le=1.0)
    valves_per_stream_max: int = Field(default=2, ge=0)
    p_control_loop: float = Field(default=0.5, ge=0.0, le=1.0)
    equipment_weights: dict[str, float] = Field(
        default_factory=lambda: dict.fromkeys(sorted(schema.EQUIPMENT_CLASSES), 1.0)
    )
    fluid_codes: list[str] = Field(default_factory=lambda: ["PL", "PG"], min_length=1)

    @model_validator(mode="after")
    def _check_equipment_range(self) -> GeneratorConfig:
        if self.equipment_per_unit_min > self.equipment_per_unit_max:
            raise ValueError(
                "equipment_per_unit_min must not exceed equipment_per_unit_max; got "
                f"min={self.equipment_per_unit_min}, max={self.equipment_per_unit_max}"
            )
        return self

    @field_validator("equipment_weights")
    @classmethod
    def _check_equipment_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        unknown = sorted(set(weights) - schema.EQUIPMENT_CLASSES)
        if unknown:
            raise ValueError(
                f"equipment_weights has unknown node_class(es) {unknown}; "
                f"expected a subset of {sorted(schema.EQUIPMENT_CLASSES)}"
            )
        non_positive = {name: value for name, value in weights.items() if value <= 0}
        if non_positive:
            raise ValueError(
                f"equipment_weights must be strictly positive; got non-positive {non_positive}"
            )
        return weights


class ValveSpec(BaseModel):
    """A valve built into a pipe segment (`stream`) — one item of `PlantBuilder.add_stream`."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    node_class: str
    tag: str


class LoopSpec(BaseModel):
    """A control loop's raw building blocks — for `PlantBuilder.add_control_loop`.

    `variable`, `unit_no`, and `loop_no` together produce the instrument tags
    (`f"{variable}T-{unit_no}-{loop_no}"` and its siblings, `plant-generator.md`
    §3.3 "Ids and tags") and the operated valve's tag (`control_valve_tag`,
    ADR-0044) — so there is no separate tag field here, the backend computes
    them. The actuator (`af_id`) carries no tag of its own.
    """

    model_config = ConfigDict(frozen=True)

    equipment_id: str
    valve_id: str
    variable: str
    unit_no: int
    loop_no: int
    psgf_id: str
    pif_id: str
    af_id: str


def control_valve_tag(variable: str, unit_no: int, loop_no: int) -> str:
    """The tag of the valve a control loop operates, e.g. `FV-30-6` (ADR-0044).

    On a real P&ID the control valve (valve body plus actuator) is printed with
    one tag whose third letter V says "valve"; both builders use this formula.
    """
    return f"{variable}V-{unit_no}-{loop_no}"


class GenerationRecord(BaseModel):
    """The generation's answer key: what came out of seed and config — **gold**, never stored.

    `generator_config` is the input `GeneratorConfig`'s JSON form, so that —
    like the manifest — a single file can reproduce the run on its own
    (together with the pyDEXPI version, for whenever the topology alone isn't enough).
    """

    plant_id: str
    seed: int
    generator_config: str
    pydexpi_version: str
    stream_kind: dict[str, StreamKind] = Field(default_factory=dict)


class PlantSummary(BaseModel):
    """Graph stats of a generated plant — regression variables for the EXP-0002 scaling sweep.

    Computed on the `DiGraph` output by `plant_graph`
    (`adapters/pydexpi_adapter.py`), never on the `DexpiModel` (`plant-generator.md` §3.2).
    """

    n_nodes: int
    n_edges: int
    nodes_per_class: dict[str, int] = Field(default_factory=dict)
    edges_per_relation: dict[str, int] = Field(default_factory=dict)
    n_units: int
    n_equipment: int
    n_streams: int
    streams_per_kind: dict[str, int] = Field(default_factory=dict)
    n_control_loops: int
    max_streams_out_of_one_equipment: int


class PlantBuilder(Protocol):
    """What a backend must be able to do, so `plan_plant` can build the topology on top of it.

    Both the pyDEXPI backend (later) and `tests/graph_plant_builder.py` (right
    now) implement this — `plan_plant` knows neither, only this contract
    (`plant-generator.md`, "Offline split of step 3").
    """

    @property
    def backend_version(self) -> str:
        """The backend's identifier — this ends up in `GenerationRecord.pydexpi_version`."""
        ...

    def add_section(self, unit_no: int) -> None:
        """Add one process unit (`PlantSection`)."""
        ...

    def add_equipment(
        self,
        node_id: str,
        node_class: str,
        unit_no: int,
        tag: str,
        tag_prefix: str,
        tag_seq: int,
    ) -> None:
        """Add one piece of equipment into a unit."""
        ...

    def add_stream(
        self,
        line_number: str,
        fluid_code: str,
        src_id: str,
        dst_id: str,
        valves: Sequence[ValveSpec],
    ) -> None:
        """Add one pipe segment between two pieces of equipment, together with its valves."""
        ...

    def add_control_loop(self, loop: LoopSpec) -> None:
        """Add one control loop: sensing on the equipment, actuation on a valve."""
        ...
