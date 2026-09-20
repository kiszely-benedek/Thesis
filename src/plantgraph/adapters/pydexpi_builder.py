"""A generátor topológia-döntéseiből egy valódi pyDEXPI `DexpiModel`-t épít (§3.5).

**DEXPI** (Data Exchange in the Process Industry) egy szabványos adatmodell
P&ID-khoz; a **pyDEXPI** csomag ennek Python-osztályait adja (`ProcessPlant`,
`CentrifugalPump`, `PipingNetworkSystem`, ...). Ez a modul a `PlantBuilder`
Protocol (`generator_models.py`) pyDEXPI-backendje: minden `plan_plant`-hívást
egy vagy több pyDEXPI-objektum felvételére fordít le, explicit id-kkal — a
pyDEXPI alapértelmezése `uuid4` lenne, ami minden futtatáskor mást adna, és
elrontaná a "same seed -> same graph" ígéretet (invariáns 3, 9, 10).
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
)

#: Rögzített exportidőpont, hogy két futás ugyanazon seeddel byte-azonos
#: pyDEXPI JSON-t adjon (invariáns 9) — a valódi óra ezt elrontaná.
_FIXED_EXPORT_TIME = datetime.datetime(2026, 1, 1)


class DexpiPlantBuilder:
    """A `PlantBuilder` Protocol pyDEXPI-implementációja: felépít egy `DexpiModel`-t.

    Belső könyvtárakban tartja a már felvett szekciókat, berendezéseket és
    szelepeket a `node_id` szerint, mert a későbbi `add_stream`/`add_control_loop`
    hívások ezekre a pyDEXPI-objektumokra hivatkoznak, nem csak az id-jukra
    (pl. egy fúvóka az adott berendezés-objektumhoz kerül hozzáfűzésre).
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
        #: berendezés-id -> hányadik fúvókánál tart — a stream-végek és az
        #: érzékelő fúvóka is ebből a számlálóból kap sorszámot (§3.5)
        self._nozzle_seq: dict[str, int] = {}
        self._stream_seq = 0

    @property
    def backend_version(self) -> str:
        """A telepített pyDEXPI verziója — a `GenerationRecord.pydexpi_version` mezőjébe kerül."""
        return importlib.metadata.version("pydexpi")

    # ---- PlantBuilder Protocol ------------------------------------------------------------

    def add_section(self, unit_no: int) -> None:
        """Felvesz egy `PlantSection`-t (technológiai egységet) a `ProcessPlant` alá."""
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
        """Felvesz egy berendezést a megfelelő `PlantSection` alá, `taggedPlantItems`-be."""
        equipment_cls = _dexpi_class(node_class)
        # _dexpi_class csak a bázisosztályt (DexpiBaseModel) ismeri statikusan;
        # a node_class alapján tudjuk, hogy valójában Equipment-leszármazott jön létre
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
        """Felvesz egy csővezetéket: egy `PipingNetworkSystem`-et egyetlen szegmenssel.

        A szegmens `len(valves) + 1` `Pipe`-ból és a köztes szelepekből áll
        (`piping_toolkit.construct_new_segment`, §3.5); a rendszer szülője a
        forrás berendezés egysége, ami a generátor "a szelep a forrás
        egységéhez tartozik" szabályát (§3.3 lépés 4) DEXPI-szinten is kifejezi.
        """
        source = self._equipment_or_raise(src_id)
        target = self._equipment_or_raise(dst_id)
        self._stream_seq += 1
        stream_id = f"{self.plant_id}-L{self._stream_seq}"

        # explicit lista-típus, mert `list` invariáns: e nélkül mypy nem engedné a
        # PipingComponent/Pipe listát a szélesebb elemtípust váró paraméterekbe
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
        """Felvesz egy szabályozókört: érzékelő fúvóka, PSGF, PIF, AF, és a szelep hivatkozása.

        Az érzékelő fúvóka **saját, dedikált** fúvóka a berendezésen, nem a már
        meglévő stream-fúvóka — DEXPI nem enged berendezést `sensingLocation`-nek,
        és egy kétnél több éllel rendelkező fúvókát pyDEXPI absztrakciója nem
        vonna össze, ami a szomszédos csővezeték-élt is elveszejtené (§3.5,
        "Two construction rules the evidence forced").
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
        af = dexpi.ActuatingFunction(
            id=loop.af_id,
            actuatingFunctionNumber=f"{loop.variable}V-{loop.unit_no}-{loop.loop_no}",
            parentStructure=section,
        )
        instrumentation_toolkit.add_signal_generating_function_to_instrumentation_function(
            pif, psgf, dexpi.MeasuringLineFunction(id=f"{loop.pif_id}-ml")
        )
        instrumentation_toolkit.add_actuating_function_to_instrumentation_function(
            pif, af, dexpi.SignalLineFunction(id=f"{loop.pif_id}-sl")
        )
        reference = dexpi.OperatedValveReference(id=f"{loop.pif_id}-ov", valve=valve)
        system = dexpi.ActuatingSystem(id=f"{loop.pif_id}-as", operatedValveReference=reference)
        af.systems = system
        loop_function = dexpi.InstrumentationLoopFunction(
            id=f"{loop.pif_id}-lp",
            instrumentationLoopFunctionNumber=f"{loop.variable}-{loop.unit_no}-{loop.loop_no}",
            processInstrumentationFunctions=[pif],
        )

        # a PSGF és az AF csak a PIF kompozíciós listáin (fent, a toolkit-hívásokban)
        # válik elérhetővé a modellfában; a cm-listákra csak azt kell rátenni, ami
        # máshogy nem érné el a gyökeret (§3.5 táblázat sorrendje)
        self._conceptual_model.processInstrumentationFunctions.append(pif)
        self._conceptual_model.actuatingSystems.append(system)
        self._conceptual_model.instrumentationLoopFunctions.append(loop_function)

    def build(self) -> dexpi.DexpiModel:
        """Lezárja a felépített modellt egy `DexpiModel`-be, rögzített export-metaadatokkal."""
        return dexpi.DexpiModel(
            id=f"{self.plant_id}-model",
            conceptualModel=self._conceptual_model,
            exportDateTime=_FIXED_EXPORT_TIME,
            originatingSystemName="plantgraph",
            originatingSystemVendorName="plantgraph",
            originatingSystemVersion=importlib.metadata.version("plantgraph"),
        )

    # ---- belső segédek ----------------------------------------------------------------

    def _build_valve(self, spec: ValveSpec, fluid_code: str) -> dexpi.PipingComponent:
        valve_cls = _dexpi_class(spec.node_class)
        valve = cast(
            dexpi.PipingComponent,
            valve_cls(id=spec.node_id, pipingComponentNumber=spec.tag, fluidCode=fluid_code),
        )
        self._valves[spec.node_id] = valve
        return valve

    def _new_nozzle(self, owner: dexpi.Equipment) -> dexpi.Nozzle:
        """Új fúvókát fűz az `owner` berendezéshez, `N{sorszám}` sub-tag-gel (§3.5)."""
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
    """A séma `node_class` nevéhez tartozó pyDEXPI osztályt adja vissza."""
    cls = getattr(dexpi, node_class, None)
    if cls is None:
        raise ValueError(f"pydexpi has no class named {node_class!r}; check graph.schema.NodeClass")
    return cls  # type: ignore[no-any-return]


@dataclass(frozen=True)
class GeneratedPlant:
    """Egy lefutott generálás teljes kimenete: a pyDEXPI-modell és a megoldókulcs."""

    model: dexpi.DexpiModel
    record: GenerationRecord


def generate_plant(config: GeneratorConfig) -> GeneratedPlant:
    """Megtervez és felépít egy üzemet: `plan_plant` + `DexpiPlantBuilder.build`."""
    builder = DexpiPlantBuilder(config.plant_id)
    record = plan_plant(config, builder)
    return GeneratedPlant(model=builder.build(), record=record)
