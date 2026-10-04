"""Builds a real pyDEXPI `DexpiModel` from the generator's topology decisions (§3.5).

**DEXPI** (Data Exchange in the Process Industry) is a standard data model for
P&IDs; the **pyDEXPI** package provides its Python classes (`ProcessPlant`,
`CentrifugalPump`, `PipingNetworkSystem`, ...). This module is the pyDEXPI
backend for the `PlantBuilder` protocol (`generator_models.py`): it translates
every `plan_plant` call into adding one or more pyDEXPI objects, with explicit
ids — pyDEXPI's default would be `uuid4`, which would differ on every run and
break the "same seed -> same graph" promise (invariants 3, 9, 10).
"""

from __future__ import annotations

import datetime
import importlib.metadata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import pydexpi.dexpi_classes.pydantic_classes as dexpi
from pydexpi.toolkits import instrumentation_toolkit
from pydexpi.toolkits import piping_toolkit as piping

from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import (
    GenerationRecord,
    GeneratorConfig,
    LoopSpec,
    ValveSpec,
    control_valve_tag,
)

#: Fixed export timestamp, so two runs with the same seed produce byte-identical
#: pyDEXPI JSON (invariant 9) — a real clock would break that.
_FIXED_EXPORT_TIME = datetime.datetime(2026, 1, 1)


class DexpiPlantBuilder:
    """The pyDEXPI implementation of the `PlantBuilder` protocol: builds a `DexpiModel`.

    Keeps the sections, equipment, and valves added so far in internal
    dictionaries keyed by `node_id`, because later `add_stream`/`add_control_loop`
    calls reference these pyDEXPI objects themselves, not just their ids (e.g. a
    nozzle gets appended onto the actual equipment object).
    """

    def __init__(self, plant_id: str) -> None:
        self.plant_id = plant_id
        meta_data = dexpi.MetaData(id=f"{plant_id}-meta", drawingNumber=plant_id)
        self._conceptual_model = dexpi.ConceptualModel(id=f"{plant_id}-cm", metaData=meta_data)
        self._plant = dexpi.ProcessPlant(
            id=f"{plant_id}-plant", processPlantIdentificationCode=plant_id
        )
        self._conceptual_model.plantStructureItems.append(self._plant)

        self._sections: dict[int, dexpi.PlantSection] = {}
        self._equipment: dict[str, dexpi.Equipment] = {}
        self._valves: dict[str, dexpi.PipingComponent] = {}
        #: equipment id -> which nozzle number it's up to — stream ends and the
        #: sensing nozzle both draw their sequence number from this counter (§3.5)
        self._nozzle_seq: dict[str, int] = {}
        self._stream_seq = 0

    @property
    def backend_version(self) -> str:
        """The installed pyDEXPI version — ends up in `GenerationRecord.pydexpi_version`."""
        return importlib.metadata.version("pydexpi")

    # ---- PlantBuilder protocol ------------------------------------------------------------

    def add_section(self, unit_no: int) -> None:
        """Add a `PlantSection` (a process unit) under the `ProcessPlant`."""
        section = dexpi.PlantSection(
            id=f"{self.plant_id}-u{unit_no}",
            plantSectionIdentificationCode=str(unit_no),
            plantSectionName=f"Unit {unit_no}",
            parentStructure=self._plant,
        )
        self._conceptual_model.plantStructureItems.append(section)
        self._sections[unit_no] = section

    def add_equipment(
        self,
        node_id: str,
        node_class: str,
        unit_no: int,
        tag: str,
        tag_prefix: str,
        tag_seq: int,
    ) -> None:
        """Add one piece of equipment under its `PlantSection`, into `taggedPlantItems`."""
        equipment_cls = _dexpi_class(node_class)
        # _dexpi_class statically only knows the base class (DexpiBaseModel);
        # we know from node_class that an Equipment subclass is actually created here
        equipment = cast(
            dexpi.Equipment,
            equipment_cls(
                id=node_id,
                tagName=tag,
                tagNamePrefix=tag_prefix,
                tagNameSequenceNumber=str(tag_seq),
                parentStructure=self._sections[unit_no],
            ),
        )
        self._conceptual_model.taggedPlantItems.append(equipment)
        self._equipment[node_id] = equipment

    def add_stream(
        self,
        line_number: str,
        fluid_code: str,
        src_id: str,
        dst_id: str,
        valves: Sequence[ValveSpec],
    ) -> None:
        """Add one pipe segment: a `PipingNetworkSystem` with a single segment.

        The segment consists of `len(valves) + 1` `Pipe`s and the valves between
        them (`piping_toolkit.construct_new_segment`, §3.5); the system's parent
        is the source equipment's unit, which expresses the generator's "a valve
        belongs to the source's unit" rule (§3.3 step 4) at the DEXPI level too.
        """
        source = self._equipment_or_raise(src_id)
        target = self._equipment_or_raise(dst_id)
        self._stream_seq += 1
        stream_id = f"{self.plant_id}-L{self._stream_seq}"

        # explicit list type, since `list` is invariant: without this, mypy would
        # reject passing a PipingComponent/Pipe list into parameters expecting the wider type
        valve_objects: list[dexpi.PipingNetworkSegmentItem] = [
            self._build_valve(spec, fluid_code) for spec in valves
        ]
        pipes: list[dexpi.PipingConnection] = [
            dexpi.Pipe(id=f"{stream_id}-pp{i}") for i in range(1, len(valve_objects) + 2)
        ]
        segment = piping.construct_new_segment(
            valve_objects,
            pipes,
            source_connector_item=self._new_nozzle(source),
            target_connector_item=self._new_nozzle(target),
            connectivity_convention=piping.PipingConnectionConvention.USE_ITEMS,
            id=f"{stream_id}-sg",
            fluidCode=fluid_code,
        )
        system = dexpi.PipingNetworkSystem(
            id=f"{stream_id}-ps",
            lineNumber=line_number,
            fluidCode=fluid_code,
            segments=[segment],
            parentStructure=source.parentStructure,
        )
        self._conceptual_model.pipingNetworkSystems.append(system)

    def add_control_loop(self, loop: LoopSpec) -> None:
        """Add one control loop: sensing nozzle, PSGF, PIF, AF, and the valve reference.

        The operated valve is renamed to the loop's valve tag (ADR-0044).

        The sensing nozzle is a **dedicated nozzle of its own** on the equipment,
        not the existing stream nozzle — DEXPI does not allow equipment as a
        `sensingLocation`, and pyDEXPI's abstraction would not consolidate a
        nozzle with more than two edges, which would also lose the neighbouring
        pipe edge (§3.5, "Two construction rules the evidence forced").
        """
        equipment = self._equipment_or_raise(loop.equipment_id)
        valve = self._valve_or_raise(loop.valve_id)
        section = self._sections[loop.unit_no]

        psgf = dexpi.ProcessSignalGeneratingFunction(
            id=loop.psgf_id,
            processSignalGeneratingFunctionNumber=f"{loop.variable}T-{loop.unit_no}-{loop.loop_no}",
            sensingLocation=self._new_nozzle(equipment),
            parentStructure=section,
        )
        pif = dexpi.ProcessInstrumentationFunction(
            id=loop.pif_id,
            processInstrumentationFunctionCategory=loop.variable,
            processInstrumentationFunctionModifier="IC",
            processInstrumentationFunctionNumber=f"{loop.unit_no}-{loop.loop_no}",
            parentStructure=section,
        )
        # the operated valve takes the loop's valve tag; the actuator carries none (ADR-0044)
        valve_tag = control_valve_tag(loop.variable, loop.unit_no, loop.loop_no)
        # the base class has no number field; the operated valves (globe, ball) all do
        cast(dexpi.GlobeValve | dexpi.BallValve, valve).pipingComponentNumber = valve_tag
        af = dexpi.ActuatingFunction(id=loop.af_id, parentStructure=section)
        instrumentation_toolkit.add_signal_generating_function_to_instrumentation_function(
            pif, psgf, dexpi.MeasuringLineFunction(id=f"{loop.pif_id}-ml")
        )
        instrumentation_toolkit.add_actuating_function_to_instrumentation_function(
            pif, af, dexpi.SignalLineFunction(id=f"{loop.pif_id}-sl")
        )
        reference = dexpi.OperatedValveReference(id=f"{loop.pif_id}-ov", valve=valve)
        system = dexpi.ActuatingSystem(
            id=f"{loop.pif_id}-as",
            actuatingSystemNumber=valve_tag,
            operatedValveReference=reference,
        )
        af.systems = system
        loop_function = dexpi.InstrumentationLoopFunction(
            id=f"{loop.pif_id}-lp",
            instrumentationLoopFunctionNumber=f"{loop.variable}-{loop.unit_no}-{loop.loop_no}",
            processInstrumentationFunctions=[pif],
        )

        # the PSGF and the AF only become reachable in the model tree through the
        # PIF's composition lists (above, in the toolkit calls); only what would
        # otherwise not reach the root needs adding to the cm lists (§3.5 table order)
        self._conceptual_model.processInstrumentationFunctions.append(pif)
        self._conceptual_model.actuatingSystems.append(system)
        self._conceptual_model.instrumentationLoopFunctions.append(loop_function)

    def build(self) -> dexpi.DexpiModel:
        """Seal the built-up model into a `DexpiModel`, with fixed export metadata."""
        return dexpi.DexpiModel(
            id=f"{self.plant_id}-model",
            conceptualModel=self._conceptual_model,
            exportDateTime=_FIXED_EXPORT_TIME,
            originatingSystemName="plantgraph",
            originatingSystemVendorName="plantgraph",
            originatingSystemVersion=importlib.metadata.version("plantgraph"),
        )

    # ---- internal helpers ----------------------------------------------------------------

    def _build_valve(self, spec: ValveSpec, fluid_code: str) -> dexpi.PipingComponent:
        valve_cls = _dexpi_class(spec.node_class)
        valve = cast(
            dexpi.PipingComponent,
            valve_cls(id=spec.node_id, pipingComponentNumber=spec.tag, fluidCode=fluid_code),
        )
        self._valves[spec.node_id] = valve
        return valve

    def _new_nozzle(self, owner: dexpi.Equipment) -> dexpi.Nozzle:
        """Attach a new nozzle to the `owner` equipment, with an `N{sequence}` sub-tag (§3.5)."""
        seq = self._nozzle_seq.get(owner.id, 0) + 1
        self._nozzle_seq[owner.id] = seq
        nozzle = dexpi.Nozzle(id=f"{owner.id}-nz{seq}", subTagName=f"N{seq}")
        owner.nozzles.append(nozzle)
        return nozzle

    def _equipment_or_raise(self, node_id: str) -> dexpi.Equipment:
        try:
            return self._equipment[node_id]
        except KeyError:
            raise ValueError(
                f"add_stream/add_control_loop refers to equipment {node_id!r}, "
                "which was never added via add_equipment"
            ) from None

    def _valve_or_raise(self, node_id: str) -> dexpi.PipingComponent:
        try:
            return self._valves[node_id]
        except KeyError:
            raise ValueError(
                f"add_control_loop refers to valve {node_id!r}, "
                "which was never added via add_stream"
            ) from None


def _dexpi_class(node_class: str) -> type[dexpi.DexpiBaseModel]:
    """Return the pyDEXPI class belonging to the schema's `node_class` name."""
    cls = getattr(dexpi, node_class, None)
    if cls is None:
        raise ValueError(f"pydexpi has no class named {node_class!r}; check graph.schema.NodeClass")
    return cls  # type: ignore[no-any-return]


@dataclass(frozen=True)
class GeneratedPlant:
    """The complete output of a generation run: the pyDEXPI model and the answer key."""

    model: dexpi.DexpiModel
    record: GenerationRecord


def generate_plant(config: GeneratorConfig) -> GeneratedPlant:
    """Plan and build a plant: `plan_plant` + `DexpiPlantBuilder.build`."""
    builder = DexpiPlantBuilder(config.plant_id)
    record = plan_plant(config, builder)
    return GeneratedPlant(model=builder.build(), record=record)
