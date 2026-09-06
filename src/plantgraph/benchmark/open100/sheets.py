"""Nyilvántartás arról, melyik OPEN100 fájl melyik rajzot tartalmazza.

A PID2Graph adathalmaz a 12 OPEN100 rajzot csupasz 0.png .. 11.png néven adja,
minden kísérő adat nélkül. Márpedig ahhoz, hogy egy csatlakozó hivatkozását
("folytatás a 120-as rajz 1. lapján") fel tudjuk oldani, tudni kell, hogy a 120-as
rajz melyik fájlban van. Ezt a hozzárendelést tartja nyilván ez a modul.

Az adatok a rajzok fejlécéből (title block) származnak, 2026-08-25-én olvastuk ki
őket; a bizonyítékot lásd a docs/private/10-literature/pid2graph.md fájlban.

Mind a 12 lap egyetlen üzemhez tartozik: az Energy Impact Center OPEN 100
atomerőmű-tervéhez, azonos szerzővel és dátummal. Négy rendszer két-két lapra
terjed ki — ezek adják a legbiztosabb lapközi hivatkozásokat.
"""

from __future__ import annotations

from pydantic import BaseModel

from plantgraph.benchmark.models import SheetRef


class Open100Sheet(BaseModel):
    """Egy OPEN100 rajz: melyik fájl, melyik rendszer, és a sorozat hányadik lapja."""

    file_stem: str
    system: str
    pid: str
    sheet_no: int
    sheet_count: int

    @property
    def ref(self) -> SheetRef:
        """A lap hivatkozási alakja, ahogy a csatlakozók feliratai hivatkoznak rá."""
        return SheetRef(pid=self.pid, sheet_no=self.sheet_no)


_ROWS: tuple[tuple[str, str, str, int, int], ...] = (
    # fájlnév, rendszer neve, P&ID szám, hányadik lap, összesen hány lap
    ("0", "Main Steam System", "140", 1, 1),
    ("1", "Air Cooled Condenser", "150", 1, 1),
    ("2", "Condensate System", "160", 1, 1),
    ("3", "Feedwater System", "170", 1, 2),
    ("4", "Extraction Steam System", "180", 1, 1),
    ("5", "Reactor Coolant System", "100", 1, 2),
    ("6", "Reactor Coolant System", "100", 2, 2),
    ("7", "Aux Cooling Water System", "210", 1, 2),
    ("8", "Aux Cooling Water System", "210", 2, 2),
    ("9", "Residual Heat Removal System", "120", 2, 2),
    ("10", "Chemical Volume Cooling Water", "110", 1, 1),
    ("11", "Residual Heat Removal System", "120", 1, 2),
)

SHEETS: dict[str, Open100Sheet] = {
    stem: Open100Sheet(file_stem=stem, system=system, pid=pid, sheet_no=sheet_no, sheet_count=count)
    for stem, system, pid, sheet_no, count in _ROWS
}

# Visszakereső index: rajz-hivatkozásból fájl. Szándékosan hiányos — a 170-es
# rendszer 2. lapjára hivatkoznak a rajzok, de az nincs az adathalmazban.
BY_REF: dict[str, Open100Sheet] = {s.ref.canonical(): s for s in SHEETS.values()}

# Rendszerek, amelyekre a 12 lap hivatkozik, de a rajzuk nincs a birtokunkban.
# Ezekből lesznek a valódi "lógó" hivatkozások: olyan kérdések, amelyekre a helyes
# válasz az, hogy nem tudjuk. Nem hiba, hanem hasznos teszteset.
#
# A 2026-08-25-i áttekintés csak 190/240/290-et azonosított; a 2026-08-31-i
# kézi feliratolvasás (stage 2) találta a többit. A 320-as szám két különböző
# névvel is előfordul a rajzokon ("RAD WASTE SYSTEM" és "CHEMICAL ADDITION
# SYSTEM") — vagy egy közös épület két rendszeréről van szó, vagy elgépelés;
# egyik esetben sem tudjuk feloldani, tehát a megkülönböztetés itt nem számít.
KNOWN_ABSENT: dict[str, str] = {
    "130": "Service Water System",
    "190": "High Pressure Steam Drains",
    "240": "Turbine System",
    "250": "Turbine Exhaust",
    "270": "Waste Process System",
    "290": "Water Sample System",
    "300": "Make-Up Water",
    "320": "Rad Waste / Chemical Addition System",
}


def resolve(ref: SheetRef) -> Open100Sheet | None:
    """Megkeresi, melyik fájlban van a hivatkozott rajz.

    Returns:
        A lap, vagy None, ha a hivatkozott rajz nincs az adathalmazban — ez utóbbi
        várható és megengedett eset, lásd KNOWN_ABSENT.
    """
    return BY_REF.get(ref.canonical())
