"""The hidden pressure levels of a v2.2 plant (design generator-v2-2 6.2, decision D3).

A **pressure level** is an ordinal rank (vacuum, atmospheric, low, medium, high), never a value or a
unit. The generator derives one for every run of pipe and every vessel *after* the plan is
finished, from the plan alone: nothing is drawn, so no random stream moves and the plan itself
carries no level. The rule checks read the result from `HiddenDesignState.segment_level`.

Key of the map: the number of a **run** (a stretch of pipe with one line number) or the node id of
a **vessel** (its own level). Rules, in the order the flow meets them:

- a tank, and every utility header, has a declared level (`UTILITY_LEVEL`);
- a pump or compressor lifts the level (by 1 and 2), an air ejector or vacuum pump by 1;
- a vessel lets the stream down one level at its inlet (a feed is never at the vessel's own
  pressure), exchangers, filters and mixers keep it, and a letdown break lowers it by one;
- the pipe pulled by a vacuum machine is at vacuum.
"""

from __future__ import annotations

from dataclasses import dataclass

from plantgraph.benchmark.v2.hidden_state import PressureLevel
from plantgraph.benchmark.v2.plan_models import LineSpec, StreamKindV2
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.trims_machine import DISCHARGE_BREAK_ROLE
from plantgraph.graph.schema import NodeClass

#: declared levels of the utility networks (design 6.2); every other service is a process line
UTILITY_LEVEL: dict[str, PressureLevel] = {
    "CWS": PressureLevel.LP,
    "CWR": PressureLevel.ATM,
    "LPS": PressureLevel.LP,
    "MPS": PressureLevel.MP,
    "CD": PressureLevel.ATM,
    "FG": PressureLevel.LP,
    "FL": PressureLevel.ATM,
    "CHD": PressureLevel.ATM,
}
PROCESS_SERVICES = frozenset({"P", "PG"})  # process liquid and process gas

PUMP_CLASSES = frozenset(
    {
        NodeClass.CENTRIFUGAL_PUMP.value,
        NodeClass.RECIPROCATING_PUMP.value,
        NodeClass.ROTARY_PUMP.value,
    }
)
COMPRESSOR_CLASSES = frozenset(
    {
        NodeClass.CENTRIFUGAL_COMPRESSOR.value,
        NodeClass.RECIPROCATING_COMPRESSOR.value,
        NodeClass.ROTARY_COMPRESSOR.value,
    }
)
EJECTOR_CLASS = NodeClass.AIR_EJECTOR.value
VACUUM_PUMP_ROLE = "liquid_ring_pump"  # a rotary compressor that draws a vacuum
#: vessels with a free surface; each lets the stream down one level (a tank is fixed at ATM)
VESSEL_CLASSES = frozenset(
    {
        NodeClass.TANK.value,
        NodeClass.PRESSURE_VESSEL.value,
        NodeClass.PROCESS_COLUMN.value,
        NodeClass.GRAVITATIONAL_SEPARATOR.value,
        NodeClass.SCRUBBING_SEPARATOR.value,
    }
)
_BREAK = NodeClass.PROPERTY_BREAK.value


def is_mover(node_class: str, role: str | None) -> bool:
    """True for a pump, compressor, air ejector or vacuum pump: the parts that lift the level."""
    return (
        node_class in PUMP_CLASSES
        or node_class in COMPRESSOR_CLASSES
        or node_class == EJECTOR_CLASS
        or role == VACUUM_PUMP_ROLE
    )


def is_vacuum_machine(node_class: str, role: str | None) -> bool:
    """True for an air ejector or a vacuum pump: what it pulls on is at vacuum."""
    return node_class == EJECTOR_CLASS or role == VACUUM_PUMP_ROLE


def lift_of(node_class: str, role: str | None) -> int:
    """How many levels a mover raises the stream: pumps 1, compressors 2, vacuum machines 1."""
    return 2 if node_class in COMPRESSOR_CLASSES and role != VACUUM_PUMP_ROLE else 1


@dataclass(frozen=True)
class _Run:
    """One stretch of pipe with a single line number (`LineSpec.runs`)."""

    number: str
    fluid: str
    src: str | None
    dst: str | None
    items: tuple[str, ...]
    kind: StreamKindV2


class _PlanIndex:
    """The plan's runs, with the lookups the assignment needs (by node, by item)."""

    def __init__(self, plan: PlantPlanV2) -> None:
        self.runs: list[_Run] = []
        self.class_of: dict[str, str] = {}
        self.role_of: dict[str, str] = {}
        for unit in plan.units:
            inner = unit.instance.plan
            self.role_of.update(inner.roles)
            self.class_of.update({e.node_id: e.node_class for e in inner.equipment})
            for line in inner.lines:
                self.class_of.update({i.node_id: i.node_class for i in line.items})
                self.runs += self._runs_of(line, inner.stream_kinds)
        #: every piece of equipment in plan order (a set would make the assignment order vary)
        self.equipment_ids = [e.node_id for u in plan.units for e in u.instance.plan.equipment]
        self.equipment = set(self.equipment_ids)
        self.run_of_item = {item: run for run in self.runs for item in run.items}
        self.into: dict[str, list[_Run]] = {}  # equipment id -> the runs that end at it
        self.joining: dict[str, list[_Run]] = {}  # item id -> the runs that end at that item
        for run in self.runs:
            if run.dst is not None:
                table = self.into if run.dst in self.equipment else self.joining
                table.setdefault(run.dst, []).append(run)

    @staticmethod
    def _runs_of(line: LineSpec, kinds: dict[str, StreamKindV2]) -> list[_Run]:
        kind = kinds[line.line_number]
        return [
            _Run(
                r.line_number,
                line.fluid_code,
                r.src_id,
                r.dst_id,
                tuple(i.node_id for i in r.items),
                kind,
            )
            for r in line.runs()
        ]

    def role(self, node_id: str) -> str | None:
        return self.role_of.get(node_id)

    def moves_fluid(self, node_id: str) -> bool:
        return is_mover(self.class_of[node_id], self.role(node_id))


class _Assigner:
    """Resolves the level of every run and vessel, sweeping until nothing more can be decided."""

    def __init__(self, index: _PlanIndex) -> None:
        self.index = index
        self.run_level: dict[str, PressureLevel] = {}
        self.node_level: dict[str, PressureLevel] = {}  # every piece of equipment but the movers
        self.allow_partial = False  # a loop (a reboiler return) is entered with what is known

    def assign(self) -> dict[str, PressureLevel]:
        """The level of every run (by number) and every vessel (by node id)."""
        while len(self.run_level) < len(self.index.runs):
            if not (self._sweep() or self._settle_stalled()):
                open_runs = [r.number for r in self.index.runs if r.number not in self.run_level]
                raise ValueError(
                    f"expected a pressure level for every run, none for {open_runs[:5]}"
                )
        self.allow_partial = True
        vessels = [n for n in self.index.equipment_ids if self.index.class_of[n] in VESSEL_CLASSES]
        levels = {n: level for n in vessels if (level := self._equipment_level(n)) is not None}
        return {**self.run_level, **levels}

    # ---- sweeping ---------------------------------------------------------------------------

    def _sweep(self) -> bool:
        """One pass over the runs not yet decided; True when at least one got its level."""
        progress = False
        for run in self.index.runs:
            if run.number in self.run_level:
                continue
            level = self._level_of(run)
            if level is not None:
                self.run_level[run.number] = level
                progress = True
        return progress

    def _settle_stalled(self) -> bool:
        """Break a stall in a loop (a reboiler return) or at an unsupplied inlet from outside.

        One piece of equipment in the loop takes the levels known so far; failing that, an inlet
        from outside the drawing gets the atmospheric level.
        """
        self.allow_partial = True
        for equipment in self.index.equipment_ids:
            if equipment not in self.node_level and not self.index.moves_fluid(equipment):
                if self._equipment_level(equipment) is not None:
                    self.allow_partial = False
                    return True
        self.allow_partial = False
        for run in self.index.runs:
            if run.number not in self.run_level and run.src is None:
                self.run_level[run.number] = PressureLevel.ATM
                return True
        return False

    # ---- one run ----------------------------------------------------------------------------

    def _level_of(self, run: _Run) -> PressureLevel | None:
        if run.fluid in UTILITY_LEVEL:
            return UTILITY_LEVEL[run.fluid]
        if run.fluid not in PROCESS_SERVICES:
            raise ValueError(
                f"expected a process or utility service, got {run.fluid!r} on {run.number}"
            )
        if self._pulled_by_vacuum_machine(run):
            return PressureLevel.VAC
        if run.src is None:
            return self._level_entering(run)
        if run.src in self.index.equipment:
            return self._level_leaving(run, run.src)
        return self._level_behind(run, run.src)

    def _pulled_by_vacuum_machine(self, run: _Run) -> bool:
        dst = run.dst
        return dst in self.index.equipment and is_vacuum_machine(
            self.index.class_of[dst], self.index.role(dst)
        )

    def _level_entering(self, run: _Run) -> PressureLevel | None:
        """A run with no source: the level of the run that joins its first part, or of its vessel.

        A run that nothing joins comes from outside the drawing and arrives at the level of the
        vessel it feeds.
        """
        feeders = self.index.joining.get(run.items[0], [])
        if feeders:
            known = [self.run_level[f.number] for f in feeders if f.number in self.run_level]
            return min(known) if len(known) == len(feeders) else None
        if run.dst in self.index.equipment and self.index.class_of[run.dst] in VESSEL_CLASSES:
            return self._equipment_level(run.dst)
        return None

    def _level_leaving(self, run: _Run, equipment: str) -> PressureLevel | None:
        """A run that starts at a piece of equipment: a mover lifts, anything else keeps."""
        if not self.index.moves_fluid(equipment):
            return self._equipment_level(equipment)
        suction = self._feed_level(equipment)
        if suction is None or run.items and self.index.role(run.items[-1]) == DISCHARGE_BREAK_ROLE:
            return suction  # the stub up to the spec break stays at the suction level
        return self._raised(suction, equipment)

    def _level_behind(self, run: _Run, item: str) -> PressureLevel | None:
        """A run that starts at a part of another run.

        A tee carries that run's level on; a spec break raises it behind a machine (a pump or
        compressor) and lowers it behind a letdown.
        """
        parent = self.index.run_of_item[item]
        level = self.run_level.get(parent.number)
        if level is None or self.index.class_of[item] != _BREAK:
            return level
        if self.index.role(item) == DISCHARGE_BREAK_ROLE:
            return self._raised(level, parent.src)
        return PressureLevel(max(level - 1, PressureLevel.ATM))

    # ---- equipment --------------------------------------------------------------------------

    def _equipment_level(self, equipment: str) -> PressureLevel | None:
        """A vessel, exchanger or filter stands at its feed level, a vessel one level below it."""
        if equipment in self.node_level:
            return self.node_level[equipment]
        node_class = self.index.class_of[equipment]
        if node_class == NodeClass.TANK.value:
            level = PressureLevel.ATM
        else:
            fed = self._feed_level(equipment)
            if fed is None:
                return None
            drop = 1 if node_class in VESSEL_CLASSES else 0
            level = PressureLevel(max(fed - drop, PressureLevel.ATM))
        self.node_level[equipment] = level
        return level

    def _feed_level(self, equipment: str) -> PressureLevel | None:
        """The lowest level among the runs that feed `equipment`; None while still unknown.

        A process run feeds; a vessel with none (a condensate pot) is fed by its utility run, and
        one fed by nothing at all stands at atmospheric.
        """
        ending = self.index.into.get(equipment, [])
        fed = [r for r in ending if self._is_feed(r)] or [
            r for r in ending if not self._is_spillback(r)
        ]
        if not fed:
            return PressureLevel.ATM
        known = [self.run_level[r.number] for r in fed if r.number in self.run_level]
        if not known or (len(known) < len(fed) and not self.allow_partial):
            return None
        return min(known)

    def _raised(self, level: PressureLevel, machine: str | None) -> PressureLevel:
        if machine is None:
            raise ValueError("expected a machine to raise the level behind a discharge break")
        lift = lift_of(self.index.class_of[machine], self.index.role(machine))
        return PressureLevel(min(level + lift, PressureLevel.HP))

    @staticmethod
    def _is_spillback(run: _Run) -> bool:
        return run.kind is StreamKindV2.RECYCLE

    @classmethod
    def _is_feed(cls, run: _Run) -> bool:
        """A run that sets the level of the equipment it enters: process fluid, not a spillback."""
        return run.fluid in PROCESS_SERVICES and not cls._is_spillback(run)


def assign_pressure_levels(plan: PlantPlanV2) -> dict[str, PressureLevel]:
    """The hidden level of every run (by line number) and vessel (by node id) of a v2.2 plan.

    Raises:
        ValueError: a run could not be given a level (a line with an unknown service code).
    """
    # rule PRS-MONOTONE: pumps and compressors lift the level, nothing else does (design §6.2)
    return _Assigner(_PlanIndex(plan)).assign()
