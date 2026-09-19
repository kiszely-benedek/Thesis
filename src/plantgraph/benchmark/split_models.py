"""A szintetikus splitter saját konfigurációja.

Amit csak a szintetikus splitter használ — nem kell az OPEN100 annotációnak,
amely valódi rajzokból nyeri vissza a kapcsolatokat. A két forrás közös
megoldókulcs-modelljei (`ConnectorPair`, `OffPageConnector`, `IdentityGroup`,
`SplitManifest`, ...) a `models.py`-ban maradtak; ez a modul azért vált külön
onnan, mert együtt túllépték volna a 400 soros fájlkorlátot, nem fogalmi okból
(`plant-generator.md` §5, "Things to watch"). `OffPageConnector` szándékosan
**nem** költözött ide: a `SplitManifest` (models.py) egy listája ilyen elemeket
tartalmaz, és e modul importálná a `Direction`-t a models.py-ból — a kettő
együtt körkörös importot adna.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from plantgraph.graph import schema


class NumberingScheme(str, Enum):
    """A csatlakozók felirat-konvenciója — szándékosan variálható, nem állandó.

    A splitter.md 3. fejezete szerint a lapszámozás és a feliratozás
    generátor-paraméter: ha egy downstream komponens csak az egyik alakra
    működik, azt a benchmarknak fel kell fednie, nem elrejtenie.
    """

    SEQUENTIAL = "sequential"  # pl. "SHEET-3-OPC-07"
    PID_STYLE = "pid_style"  # pl. "PID-120-1" — az OPEN100-on megfigyelt alak


class ConnectorLabelDetail(str, Enum):
    """Mennyi felirat kerül egy csatlakozó csonkra — a nehezebb EXP-0004 feltétel is választható.

    FULL alatt a csonk a partnere saját feliratát (`referenced_connector_number`)
    is megkapja. DRAWING_ONLY ezt elhagyja: a resolvernek ilyenkor a
    `line_number` és a `fluid_code` alapján kell megkülönböztetnie két,
    ugyanazon lappár közti csatlakozót (`plant-generator.md` §5, finding 2b).
    """

    FULL = "full"
    DRAWING_ONLY = "drawing_only"


class SplitConfig(BaseModel):
    """A szintetikus splitter minden beállítása — a stratégiától a feliratozási konvencióig.

    Minden itt szereplő mező szándékosan paraméter, nem beégetett állandó
    (splitter.md 3. fejezet): a kutatási kérdés pont az, hogy ezek a
    konvenciók hogyan hatnak a visszakeresés pontosságára.
    """

    strategy: str = "flow_greedy"
    sheet_equipment_budget: int = Field(default=10, ge=1)
    seed: int = 0
    duplication_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    equipment_classes: set[str] = Field(default_factory=lambda: set(schema.EQUIPMENT_CLASSES))
    numbering_scheme: NumberingScheme = NumberingScheme.SEQUENTIAL
    use_grid_reference: bool = False
    exact_match_tags: bool = True
    connector_label_detail: ConnectorLabelDetail = ConnectorLabelDetail.FULL
