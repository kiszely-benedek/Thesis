"""Adatmodell a szintetikus üzemgráf-generátorhoz (`plant-generator.md` §3.2, §3.5).

A modul két, egymástól élesen elváló dolgot ír le:

- **mit kér a felhasználó** — `GeneratorConfig`: hány egység, mennyi berendezés
  egységenként, milyen valószínűséggel kap egy egység recirkulációt (recycle)
  vagy egy másik egységből induló keresztkötést (cross-link), és így tovább.
  Minden mező itt szabadon hangolható paraméter, nem beégetett állandó
  (`plant-generator.md` §3.2 — "All defaults are arbitrary and test-sized").
- **mit kap vissza egy backend a generátor topológia-döntéseiből** —
  `ValveSpec`, `LoopSpec` a `PlantBuilder` Protocol hívásaihoz, és
  `GenerationRecord` a lefutott generálás megoldókulcsaként.

**Miért Protocol, és miért nincs itt pyDEXPI.** Az offline gépen a pyDEXPI
csomag nem telepíthető (`plant-generator.md`, "Offline split of step 3"
jegyzet). A `PlantBuilder` Protocol ezért csak azt írja le, MILYEN hívásokat
vár a topológia-tervező egy backendtől — hogy a valódi pyDEXPI-backend
később ugyanezt a Protocolt implementálhassa, a teszteké pedig
(`tests/graph_plant_builder.py`) most rögtön. `build()` szándékosan nincs a
Protocolban: az a végleges kimenet előállítása (DEXPI modell vagy gráf),
backend-specifikus lépés, nem a topológia-tervezés része.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from plantgraph.graph import schema

#: Egy berendezés-adat cellája: szöveg (pl. leírás), vagy (érték, mértékegység)
#: pár egy DEXPI mennyiséghez (`plant-generator.md` §3.5, §4.8). A generátor
#: jelenleg üres mappinget ad át (`equipment_data` egyelőre figyelmen kívül
#: marad, lásd `GeneratorConfig.equipment_data`), de a típus már most rögzített,
#: hogy a builder-hívás aláírása ne változzon, amikor a 3b lépés bekapcsolja.
DataValue = str | tuple[float, str]


class StreamKind(str, Enum):
    """Egy csővezeték (`stream`, két berendezés közti anyagáram) honnan ered a topológiában.

    Csak elemzési célra kerül a megoldókulcsba (`GenerationRecord`) — a
    generált gráfban a `stream_kind` tulajdonság **gold**, sosem a
    visszakeresés alatt álló tárban (`plant-generator.md` §4.4).
    """

    TREE = "tree"  # az egységen belüli véletlen fa éle
    RECYCLE = "recycle"  # egy későbbi berendezéstől vissza egy korábbihoz, ugyanazon egységen belül
    CROSS_UNIT = "cross_unit"  # az egységek láncolatát biztosító kötelező kereszt-áram
    CROSS_LINK = "cross_link"  # egy korábbi egységből induló, nem kötelező extra kereszt-áram


class GeneratorConfig(BaseModel):
    """A szintetikus üzemgráf-generátor minden beállítása (`plant-generator.md` §3.2).

    Minden alapérték önkényes és teszt-méretű; egyik sem állítás valódi
    üzemekről. `equipment_data` mezőt a generátor jelenleg elfogadja, de nem
    használja (a step 3b vezeti majd be a berendezés-adatok kitöltését).
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
    equipment_data: bool = True

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
    """Egy csővezetékbe (`stream`) beépített szelep — a `PlantBuilder.add_stream` egy eleme."""

    model_config = ConfigDict(frozen=True)

    node_id: str
    node_class: str
    tag: str


class LoopSpec(BaseModel):
    """Egy szabályozókör (control loop) nyers alkotóelemei — `PlantBuilder.add_control_loop`-nak.

    A `variable`, `unit_no` és `loop_no` együtt adja ki a három műszer-tag-et
    (`f"{variable}T-{unit_no}-{loop_no}"` és társai,
    `plant-generator.md` §3.3 "Ids and tags") — ezért nincs itt külön tag mező,
    a backend számolja ki a formulából.
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


class GenerationRecord(BaseModel):
    """A generálás megoldókulcsa: a seedből és a configból mi lett — **gold**, sosem a tár alatt.

    `generator_config` a bemenő `GeneratorConfig` JSON-alakja, hogy a
    manifeszthez hasonlóan egyetlen fájl önmagában is reprodukálja a futást
    (a pyDEXPI-verzióval együtt, amikortól a topológia nem elég).
    """

    plant_id: str
    seed: int
    generator_config: str
    pydexpi_version: str
    stream_kind: dict[str, StreamKind] = Field(default_factory=dict)


class PlantSummary(BaseModel):
    """Egy legenerált üzem gráf-jellemzői — az EXP-0002 skálázási sweep regressziós változói.

    A `plant_graph` (`adapters/pydexpi_adapter.py`) kimenő `DiGraph`-ján
    számolódik, sosem a `DexpiModel`-en (`plant-generator.md` §3.2).
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
    """Amit egy backendnek tudnia kell, hogy `plan_plant` fel tudja rajta építeni a topológiát.

    A pyDEXPI-backend (később) és `tests/graph_plant_builder.py` (most) egyaránt
    ezt implementálja — `plan_plant` egyiket sem ismeri, csak ezt a szerződést
    (`plant-generator.md`, "Offline split of step 3").
    """

    @property
    def backend_version(self) -> str:
        """A backend azonosítója — ez kerül a `GenerationRecord.pydexpi_version` mezőjébe."""
        ...

    def add_section(self, unit_no: int) -> None:
        """Felvesz egy technológiai egységet (`PlantSection`)."""
        ...

    def add_equipment(
        self,
        node_id: str,
        node_class: str,
        unit_no: int,
        tag: str,
        tag_prefix: str,
        tag_seq: int,
        data: Mapping[str, DataValue],
    ) -> None:
        """Felvesz egy berendezést egy egységbe."""
        ...

    def add_stream(
        self,
        line_number: str,
        fluid_code: str,
        src_id: str,
        dst_id: str,
        valves: Sequence[ValveSpec],
    ) -> None:
        """Felvesz egy csővezetéket két berendezés között, a rajta lévő szelepekkel együtt."""
        ...

    def add_control_loop(self, loop: LoopSpec) -> None:
        """Felvesz egy szabályozókört: érzékelés a berendezésen, avatkozás egy szelepen."""
        ...
