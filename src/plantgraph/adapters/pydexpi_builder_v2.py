"""Builds a real pyDEXPI `DexpiModel` from the v2 planner's specs (generator-v2-realism.md, V2-T4).

The v2 backend of the `PlantBuilderV2` protocol (`benchmark/v2/plan_models.py`): every call adds
pyDEXPI objects with explicit ids (pyDEXPI's default is `uuid4`, which would differ on every run
and break "same seed, same graph"). A spec's `node_id` is the id of its DEXPI object, so the graph
node ids equal the plan's ids. Helper objects (pipes, nozzles, signal lines) derive their ids from
the spec ids or from a counter; planners must not use ids like `<plant_id>-L3`.

Machines get an electric motor component (`has_motor`), a vessel gets its agitator
(`has_agitator` link), an `ActuatingElectricalFunction` starts a machine (`control` link) and a
`PropertyBreak` sits inline on a line. Helpers for these are in `pydexpi_builder_v2_equipment.py`.
"""

from __future__ import annotations

import datetime
import importlib.metadata
from typing import cast

import pydexpi.dexpi_classes.pydantic_classes as dexpi

from plantgraph.adapters.pydexpi_builder_v2_equipment import (
    attach_agitator,
    attach_machine,
    create_equipment,
)
from plantgraph.adapters.pydexpi_builder_v2_instruments import (
    Instrument,
    connect_signal,
    create_actuating_system,
    create_carrier,
    create_instrument,
)
from plantgraph.adapters.pydexpi_builder_v2_lines import (
    build_line_system,
    create_line_item,
    line_list_fields,
)
from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    InstrumentSpec,
    LineRun,
    LineSpec,
    LinkSpec,
)
from plantgraph.graph import schema
from plantgraph.graph.schema import NodeClass, Relation

#: the node classes of an actuator: a valve's (AF) or a machine's start/stop (AEF)
_ACTUATOR_CLASSES = frozenset(
    {NodeClass.ACTUATING_FUNCTION.value, NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value}
)

#: Fixed export timestamp, so two runs of one plan give byte-identical JSON (as in the v1 builder).
_FIXED_EXPORT_TIME = datetime.datetime(2026, 1, 1)


class DexpiPlantBuilderV2:
    """The pyDEXPI implementation of `PlantBuilderV2`: builds a `DexpiModel`."""

    def __init__(self, plant_id: str) -> None:
        self.plant_id = plant_id
        meta_data = dexpi.MetaData(id=f"{plant_id}-meta", drawingNumber=plant_id)
        self._model = dexpi.ConceptualModel(id=f"{plant_id}-cm", metaData=meta_data)
        self._plant = dexpi.ProcessPlant(
            id=f"{plant_id}-plant", processPlantIdentificationCode=plant_id
        )
        self._model.plantStructureItems.append(self._plant)
        self._sections: dict[int, dexpi.PlantSection] = {}
        self._equipment: dict[str, dexpi.Equipment] = {}
        self._items: dict[str, dexpi.PipingNetworkSegmentItem] = {}  # inline parts, by plan id
        self._item_classes: dict[str, str] = {}
        self._instruments: dict[str, Instrument] = {}
        self._instrument_specs: dict[str, InstrumentSpec] = {}
        self._sensors_with_bubble: set[str] = set()
        self._actuated_valves: set[str] = set()
        self._motor_driven: set[str] = set()  # ids of machines with a motor component
        self._agitators_taken: set[str] = set()  # agitators already assigned to a vessel
        self._signalled_actuators: set[str] = set()  # AEFs fed by a bubble
        self._nozzle_seq: dict[str, int] = {}
        self._line_seq = 0

    @property
    def backend_version(self) -> str:
        """The installed pyDEXPI version; ends up in `GenerationRecordV2.pydexpi_version`."""
        return importlib.metadata.version("pydexpi")

    # ---- PlantBuilderV2 protocol ----------------------------------------------------------------

    def add_section(self, unit_no: int, name: str) -> None:
        """Add a `PlantSection` (a process unit) under the `ProcessPlant`."""
        if unit_no in self._sections:
            raise ValueError(f"unit {unit_no} was added twice")
        section = dexpi.PlantSection(
            id=f"{self.plant_id}-u{unit_no}",
            plantSectionIdentificationCode=str(unit_no),
            plantSectionName=name,
            parentStructure=self._plant,
        )
        self._model.plantStructureItems.append(section)
        self._sections[unit_no] = section

    def add_equipment(self, spec: EquipmentSpec) -> None:
        """Add one piece of equipment under its `PlantSection`, into `taggedPlantItems`."""
        self._require_new_id(spec.node_id)
        if spec.node_class not in schema.EQUIPMENT_CLASSES:
            raise ValueError(
                f"expected an equipment class for {spec.node_id!r}, got {spec.node_class!r}"
            )
        equipment = create_equipment(spec, self._section(spec.unit_no))
        self._model.taggedPlantItems.append(equipment)
        self._equipment[spec.node_id] = equipment
        if spec.has_motor:
            self._motor_driven.add(spec.node_id)

    def add_line(self, spec: LineSpec) -> None:
        """Add one line: a `PipingNetworkSystem` per run (two when the line has a spec break)."""
        section = self._section(spec.unit_no)
        for run in spec.runs():
            self._add_run(run, spec.fluid_code, section)

    def _add_run(self, run: LineRun, fluid_code: str, section: dexpi.PlantSection) -> None:
        """One run: a system with a single segment and its inline parts."""
        line_list = line_list_fields(run.line_number)  # validate before anything is built
        source_owner = self._line_end_owner(run.src_id, run, "src_id")
        target_owner = self._line_end_owner(run.dst_id, run, "dst_id")
        items = [create_line_item(item, fluid_code) for item in run.items]
        for item_spec in run.items:  # before anything is registered
            self._require_new_id(item_spec.node_id)
        self._require_distinct_ids([item_spec.node_id for item_spec in run.items])
        self._line_seq += 1
        system = build_line_system(
            f"{self.plant_id}-L{self._line_seq}",
            fluid_code,
            section,
            line_list,
            items,
            self._line_connector(source_owner),
            self._line_connector(target_owner),
        )
        self._model.pipingNetworkSystems.append(system)
        for item_spec, part in zip(run.items, items, strict=True):
            self._items[item_spec.node_id] = part
            self._item_classes[item_spec.node_id] = item_spec.node_class

    def add_instrument(self, spec: InstrumentSpec) -> None:
        """Add one sensor, bubble or actuator; it joins the model through `add_link`."""
        self._require_new_id(spec.node_id)
        instrument = create_instrument(spec, self._section(spec.unit_no))
        self._instruments[spec.node_id] = instrument
        self._instrument_specs[spec.node_id] = spec
        if isinstance(instrument, dexpi.ProcessInstrumentationFunction):
            self._model.processInstrumentationFunctions.append(instrument)

    def add_link(self, spec: LinkSpec) -> None:
        """Add a sensing, a signal or an actuation; both ends must exist already."""
        if spec.relation is Relation.MEASURED_BY:
            self._link_measurement(spec)
        elif spec.relation is Relation.SEND_SIGNAL_TO:
            self._link_signal(spec)
        elif spec.relation is Relation.CONTROL:
            self._link_control(spec)
        elif spec.relation is Relation.HAS_AGITATOR:
            self._link_agitator(spec)
        else:
            raise ValueError(f"expected a link relation the builder knows, got {spec.relation}")

    def build(self) -> dexpi.DexpiModel:
        """Seal the model: wrap lone sensors, check nothing dangles, return the `DexpiModel`."""
        self._seal()
        return dexpi.DexpiModel(
            id=f"{self.plant_id}-model",
            conceptualModel=self._model,
            exportDateTime=_FIXED_EXPORT_TIME,
            originatingSystemName="plantgraph",
            originatingSystemVendorName="plantgraph",
            originatingSystemVersion=importlib.metadata.version("plantgraph"),
        )

    # ---- lines ----------------------------------------------------------------------------------

    def _line_end_owner(
        self, node_id: str | None, run: LineRun, field: str
    ) -> dexpi.Equipment | dexpi.PipeTee | dexpi.PropertyBreak | None:
        """The equipment, pipe tee or spec break at a line end; None for an open end."""
        if node_id is None:
            return None
        if node_id in self._equipment:
            return self._equipment[node_id]
        item = self._items.get(node_id)
        if isinstance(item, dexpi.PipeTee | dexpi.PropertyBreak):
            return item
        raise ValueError(
            f"line {run.line_number!r}: {field} must name added equipment or a PipeTee on "
            f"another line (or the PropertyBreak this line continues from), got {node_id!r}"
        )

    def _line_connector(
        self, owner: dexpi.Equipment | dexpi.PipeTee | dexpi.PropertyBreak | None
    ) -> dexpi.Nozzle | dexpi.PipeTee | dexpi.PropertyBreak | None:
        """Equipment gets a fresh nozzle for this line end; a tee or a break is joined directly."""
        if isinstance(owner, dexpi.Equipment):
            return self._new_nozzle(owner)
        return owner

    def _new_nozzle(self, owner: dexpi.Equipment) -> dexpi.Nozzle:
        """A nozzle (a flanged connection on a vessel) for one line end or one sensor."""
        seq = self._nozzle_seq.get(owner.id, 0) + 1
        self._nozzle_seq[owner.id] = seq
        nozzle = dexpi.Nozzle(id=f"{owner.id}-nz{seq}", subTagName=f"N{seq}")
        owner.nozzles.append(nozzle)
        return nozzle

    # ---- links ----------------------------------------------------------------------------------

    def _link_measurement(self, spec: LinkSpec) -> None:
        """`measured_by`: the sensor's `sensingLocation` is the sensed thing.

        Equipment is sensed through a nozzle of its own (pyDEXPI keeps the edge only for a
        nozzle with one connection); a valve, flow element or flange is the location itself.
        A `PropertyBreak` cannot be sensed: pyDEXPI does not make it a sensing location.
        """
        sensor = self._sensor(spec.target_id)
        if sensor.sensingLocation is not None:
            raise ValueError(f"sensor {spec.target_id!r} already has a sensing location")
        if spec.source_id in self._equipment:
            location: dexpi.SensingLocation = self._new_nozzle(self._equipment[spec.source_id])
        elif spec.source_id in self._items:
            location = self._sensing_location(spec.source_id)
        else:
            raise ValueError(
                f"measured_by link: expected added equipment or an inline part as the sensed "
                f"thing, got {spec.source_id!r}"
            )
        sensor.sensingLocation = location

    def _sensing_location(self, node_id: str) -> dexpi.SensingLocation:
        part = self._items[node_id]
        if not isinstance(part, dexpi.SensingLocation):
            raise ValueError(
                f"measured_by link: expected a sensable inline part, got {node_id!r} "
                f"({self._item_classes[node_id]}), which pyDEXPI cannot sense"
            )
        return part

    def _link_signal(self, spec: LinkSpec) -> None:
        """`send_signal_to`: a sensor feeds a bubble, a bubble feeds an actuator or a bubble."""
        source = self._instrument(spec.source_id, "send_signal_to link source")
        target = self._instrument(spec.target_id, "send_signal_to link target")
        if spec.source_id in self._sensors_with_bubble:
            raise ValueError(f"sensor {spec.source_id!r} already feeds a bubble")
        self._check_loop_tag(spec)
        connect_signal(source, target)
        if isinstance(target, dexpi.ActuatingElectricalFunction):
            self._signalled_actuators.add(spec.target_id)
        if isinstance(source, dexpi.ProcessSignalGeneratingFunction):
            self._sensors_with_bubble.add(spec.source_id)

    def _check_loop_tag(self, spec: LinkSpec) -> None:
        """A sensor or actuator wired to a bubble must carry that bubble's tag as its loop tag.

        The adapter derives `loop_tag` from the bubble; the plan states it too, so a mismatch
        would make the DEXPI graph differ from the oracle without any error.
        """
        source = self._instrument_specs[spec.source_id]
        target = self._instrument_specs[spec.target_id]
        if source.node_class == NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value:
            bubble, member = target, source
        elif target.node_class in _ACTUATOR_CLASSES:
            bubble, member = source, target
        else:
            return  # bubble to bubble (a cascade): no single loop tag to compare
        if member.loop_tag != bubble.tag:
            raise ValueError(
                f"{member.node_id!r} is wired to {bubble.tag!r} but states loop tag "
                f"{member.loop_tag!r}; expected {bubble.tag!r}"
            )

    def _link_control(self, spec: LinkSpec) -> None:
        """`control`: an actuator operates a valve body (with its actuating system) or a machine."""
        actuator = self._instruments.get(spec.source_id)
        if isinstance(actuator, dexpi.ActuatingElectricalFunction):
            self._link_machine_control(actuator, spec)
            return
        if not isinstance(actuator, dexpi.ActuatingFunction):
            raise ValueError(
                f"control link: expected an ActuatingFunction or ActuatingElectricalFunction as "
                f"the source, got {spec.source_id!r}"
            )
        valve_class = self._item_classes.get(spec.target_id)
        if valve_class not in schema.CONTROL_VALVE_BODY_CLASSES:
            raise ValueError(
                f"control link: expected a control valve body as the target, got "
                f"{spec.target_id!r} ({valve_class})"
            )
        if spec.target_id in self._actuated_valves or actuator.systems is not None:
            raise ValueError(
                f"control link {spec.source_id!r} -> {spec.target_id!r}: already actuated"
            )
        valve = cast(dexpi.OperatedValve, self._items[spec.target_id])
        self._model.actuatingSystems.append(create_actuating_system(actuator, valve, valve_class))
        self._actuated_valves.add(spec.target_id)

    def _link_machine_control(
        self, actuator: dexpi.ActuatingElectricalFunction, spec: LinkSpec
    ) -> None:
        """`control` from an electrical actuator: it acts on a nozzle of a motor-driven machine."""
        if spec.target_id not in self._motor_driven:
            raise ValueError(
                f"control link from {spec.source_id!r}: expected a motor-driven machine "
                f"(has_motor) as the target, got {spec.target_id!r}"
            )
        attach_machine(actuator, self._new_nozzle(self._equipment[spec.target_id]))

    def _link_agitator(self, spec: LinkSpec) -> None:
        """`has_agitator`: the vessel's `agitator` field refers to an added `Agitator`."""
        for node_id in (spec.source_id, spec.target_id):
            if node_id not in self._equipment:
                raise ValueError(f"has_agitator link: expected added equipment, got {node_id!r}")
        if spec.target_id in self._agitators_taken:
            raise ValueError(f"agitator {spec.target_id!r} already stirs another vessel")
        attach_agitator(self._equipment[spec.source_id], self._equipment[spec.target_id])
        self._agitators_taken.add(spec.target_id)

    # ---- lookups and checks ---------------------------------------------------------------------

    def _section(self, unit_no: int) -> dexpi.PlantSection:
        try:
            return self._sections[unit_no]
        except KeyError:
            raise ValueError(f"unit {unit_no} was never added via add_section") from None

    def _instrument(self, node_id: str, context: str) -> Instrument:
        try:
            return self._instruments[node_id]
        except KeyError:
            raise ValueError(f"{context}: {node_id!r} was not added via add_instrument") from None

    def _sensor(self, node_id: str) -> dexpi.ProcessSignalGeneratingFunction:
        instrument = self._instrument(node_id, "measured_by link target")
        if not isinstance(instrument, dexpi.ProcessSignalGeneratingFunction):
            raise ValueError(f"measured_by link: expected a sensor as the target, got {node_id!r}")
        return instrument

    def _require_new_id(self, node_id: str) -> None:
        taken = self._equipment.keys() | self._items.keys() | self._instruments.keys()
        if node_id in taken:
            raise ValueError(f"node id {node_id!r} added twice")

    def _require_distinct_ids(self, node_ids: list[str]) -> None:
        if len(set(node_ids)) != len(node_ids):
            raise ValueError(f"a line lists the same node id twice: {sorted(node_ids)}")

    def _seal(self) -> None:
        """Wrap sensors that have no bubble; refuse sensors with no location, loose actuators."""
        for node_id, instrument in self._instruments.items():
            if isinstance(instrument, dexpi.ProcessSignalGeneratingFunction):
                self._seal_sensor(node_id, instrument)
            elif isinstance(instrument, dexpi.ActuatingFunction) and instrument.systems is None:
                raise ValueError(f"actuator {node_id!r} operates no valve; expected a control link")
            elif isinstance(instrument, dexpi.ActuatingElectricalFunction):
                self._seal_electrical_actuator(node_id, instrument)

    def _seal_electrical_actuator(
        self, node_id: str, actuator: dexpi.ActuatingElectricalFunction
    ) -> None:
        """S19: an electrical actuator acts on one machine and is fed by at least one bubble."""
        if actuator.actuatingElectricalLocation is None:
            raise ValueError(
                f"electrical actuator {node_id!r} acts on no machine; expected a control link"
            )
        if node_id not in self._signalled_actuators:
            raise ValueError(
                f"electrical actuator {node_id!r} has no signal source; "
                "expected a send_signal_to link"
            )

    def _seal_sensor(self, node_id: str, sensor: dexpi.ProcessSignalGeneratingFunction) -> None:
        if sensor.sensingLocation is None:
            raise ValueError(f"sensor {node_id!r} senses nothing; expected a measured_by link")
        if node_id in self._sensors_with_bubble:
            return
        spec = self._instrument_specs[node_id]
        if spec.loop_tag != spec.tag:
            raise ValueError(
                f"local instrument {node_id!r} is its own loop: expected loop tag {spec.tag!r}, "
                f"got {spec.loop_tag!r}"
            )
        self._model.processInstrumentationFunctions.append(create_carrier(sensor))
        self._sensors_with_bubble.add(node_id)
