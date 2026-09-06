"""Adatmodell a többlapos benchmark megoldókulcsához.

Fogalmak, mert a kód egy mérnöki szakterületről szól:

- **P&ID**: egy üzem csöveinek és műszereinek műszaki rajza. Egy teljes üzem több
  száz ilyen lapból áll.
- **lap (sheet)**: a rajzsorozat egyetlen oldala. Egy csővezeték ritkán fér el egy
  lapon, ezért átnyúlik a következőre.
- **off-page connector**: ha egy cső kifut a lap széléről, mindkét érintett lapra
  egy feliratozott nyíl kerül, amely megmondja, hol folytatódik ("folytatás a
  120-as rajz 1. lapján, a D-1 mezőben"). Ez a lapok közötti kereszthivatkozás.
- **megoldókulcs (ground truth)**: az ismerten helyes válaszok, amelyekhez a
  rendszer kimenetét mérjük.

Két forrás állítja elő a megoldókulcsot: a szintetikus splitter, amely egy
üzemgráfot vág lapokra, és az OPEN100 annotáció, amely valódi rajzokból nyeri
vissza a kapcsolatokat. Mindkettő ugyanezt a SplitManifest-et adja ki, így a
későbbi kód nem tudja megkülönböztetni a két forrást — és nem is szabad tudnia.
Lásd: docs/private/40-design/splitter.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Side(str, Enum):
    """Melyik lapszélen van a csatlakozó szimbóluma: a bal vagy a jobb.

    Csak azt rögzíti, hol van a képen — azt nem, hogy be- vagy kifelé megy rajta
    az anyag. Arra a Direction való.
    """

    LEFT = "left"
    RIGHT = "right"


class Direction(str, Enum):
    """Be- vagy kifelé áramlik-e az anyag a lapból ezen a csatlakozón át.

    Ezt a csatlakozó felirata mondja meg, nem a helyzete. A rajzolók a bejövőket
    általában balra, a kimenőket jobbra teszik, de ez csak szokás — más rajzoló
    máshogy csinálja, tehát nem szabad rá építeni.
    """

    INCOMING = "incoming"
    OUTGOING = "outgoing"


class BoundingBox(BaseModel):
    """Egy szimbólum köré húzott téglalap, a kép képpont-koordinátáiban.

    Az annotáció így jelöli meg, hol található egy elem a rajzon: bal-felső és
    jobb-alsó sarok.
    """

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @model_validator(mode="after")
    def _check_ordering(self) -> BoundingBox:
        if self.xmax <= self.xmin or self.ymax <= self.ymin:
            raise ValueError(f"degenerate box: expected xmin<xmax and ymin<ymax, got {self!r}")
        return self

    @property
    def width(self) -> float:
        """A doboz szélessége képpontban."""
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        """A doboz magassága képpontban."""
        return self.ymax - self.ymin

    @property
    def centre_x(self) -> float:
        """A doboz vízszintes középpontja — ebből dől el, melyik lapszélhez tartozik."""
        return (self.xmin + self.xmax) / 2

    def expanded(self, x_factor: float, y_margin: float) -> BoundingBox:
        """Kitágítja a dobozt: oldalra a saját szélessége szorosával, fel-le képpontban.

        Azért kell, mert a csatlakozó felirata még a dobozon belül van, de a cső
        azonosítója (a "line number", pl. SIZE-RCS-100007-SPEC-HC-X) már mellette,
        a csővezetékre írva. Ha azt is el akarjuk olvasni, oldalra ki kell nyúlni.
        """
        pad = self.width * x_factor
        return BoundingBox(
            xmin=self.xmin - pad,
            ymin=self.ymin - y_margin,
            xmax=self.xmax + pad,
            ymax=self.ymax + y_margin,
        )

    def clipped_to(self, width: int, height: int) -> BoundingBox:
        """Visszavágja a dobozt a kép határai közé, hogy a kivágás ne lógjon ki."""
        return BoundingBox(
            xmin=max(0.0, self.xmin),
            ymin=max(0.0, self.ymin),
            xmax=min(float(width), self.xmax),
            ymax=min(float(height), self.ymax),
        )

    def as_pixels(self) -> tuple[int, int, int, int]:
        """Egész koordináták (bal, felső, jobb, alsó) — a PIL crop metódusa így kéri."""
        return (round(self.xmin), round(self.ymin), round(self.xmax), round(self.ymax))


class SheetRef(BaseModel):
    """Hivatkozás egy rajzlapra: melyik P&ID, és azon belül hányadik lap.

    Ugyanarra a lapra a rajzok többféleképp hivatkoznak — az OPEN100-ban a
    'PID 120-1', a 'PID-120-01' és az 'RCS-PID-100-2' alak is előfordul. Ezért
    egységes alakra hozzuk, és csak úgy hasonlítjuk össze őket; szövegszerű
    egyezésre építeni itt hibás lenne.
    """

    pid: str
    sheet_no: int

    def canonical(self) -> str:
        """Egységes írásmód, pl. PID-120-1 — csak ezt szabad összehasonlítani."""
        return f"PID-{self.pid}-{self.sheet_no}"


class ConnectorObservation(BaseModel):
    """Egy megtalált csatlakozó szimbólum egy lapon, mindazzal, amit tudunk róla.

    Három lépésben töltjük fel:
      1. geometria — hol van a képen (ez jön az annotációs fájlból),
      2. felirat — mi van ráírva (miután a kivágást elolvastuk),
      3. verified_by_human — ellenőrizte-e valaki kézzel.

    Az opcionális mezők azt jelentik, hogy az értéket még nem ismerjük. Sosem
    töltjük fel csendben alapértelmezettel: a "nem tudom" és a "nulla" itt két
    különböző dolog.
    """

    sheet_file: str
    node_id: str
    bbox: BoundingBox
    side: Side

    raw_text: str | None = None
    direction: Direction | None = None
    target: SheetRef | None = None
    grid_cell: str | None = None
    service: str | None = None
    line_number: str | None = None

    verified_by_human: bool = False

    @property
    def key(self) -> str:
        """Stabil azonosító, amely a teljes rajzsorozaton belül egyedi."""
        return f"{self.sheet_file}:{self.node_id}"


class MatchRule(str, Enum):
    """Melyik szabály találta meg a párt — a bizonytalanabb szabályok ellenőrizhetők maradjanak.

    A rangsor a docs/private/40-design/open100-annotation.md 3. lépéséből jön:
    a sorszám maga a bizalmi szint, 1 a legerősebb.
    """

    LINE_NUMBER = "line_number"  # 1. az azonosító megegyezik mindkét lapon — ez a legerősebb jel
    GRID_MUTUAL = "grid_mutual"  # 2. a célmező mindkét irányból ugyanoda mutat
    SERVICE_DIRECTION = (
        "service_direction"  # 3. csak a rendszer és az irány egyezik — kézi ellenőrzést igényel
    )
    SYNTHETIC = "synthetic"  # a szintetikus generátor vágta el — nem kell találgatni, tudjuk


class ConnectorPair(BaseModel):
    """Két csatlakozó, amelyekről kiderült, hogy ugyanannak a csőnek a két vége.

    Ez a megoldókulcs egy sora: pontosan ezeket a párokat kell a rendszernek
    megtalálnia, és ezeken mérjük a pontosságát.

    Az original_edge csak a szintetikus generátornál van kitöltve, mert ott mi
    magunk vágtuk el a gráf élét, tehát tudjuk, mi volt. Valódi rajz annotálásakor
    a kapcsolat visszanyerhető, de az eredeti él nem — ezért marad None.

    A match_rule megmondja, mennyire kell megbízni a párban. Egy line_number
    találat egy elgépelt felirat miatt tévedhet; egy service_direction találat
    puszta egybeesés is lehet. Mindkettő bekerül a megoldókulcsba, de más súllyal.
    """

    from_key: str
    to_key: str
    line_number: str | None = None
    original_edge: tuple[str, str] | None = None
    match_rule: MatchRule = MatchRule.SYNTHETIC
    note: str | None = None


class DanglingReference(BaseModel):
    """Csatlakozó, amely olyan lapra hivatkozik, ami nincs a birtokunkban.

    Nem hiba, hanem a valóság: egy rajzsorozat majdnem mindig csak részhalmaza az
    üzemnek. Ezekből lesznek a szándékosan megválaszolhatatlan kérdések, ahol a jó
    válasz az, hogy "ez az információ nincs meg" — és nem az, hogy a rendszer
    kitalál valamit.
    """

    from_key: str
    target: SheetRef
    reason: str = "target sheet not present in corpus"


class IdentityGroup(BaseModel):
    """Egy fizikai berendezés, amelyet több lapra is felrajzoltak.

    Ugyanaz a szivattyú szerepelhet a saját rendszerének lapján és a hűtővíz
    lapján is: két rajzjel, egyetlen valódi szivattyú. A kettőt össze kell vonni.

    Ez a másik fajta lapok közötti kapcsolat, és ez a veszélyesebb. Egy kihagyott
    off-page connector látványosan kettészakadt gráfot hagy, ami feltűnik. Egy
    kihagyott azonosságnál viszont a gráf épnek látszik, csak épp két külön
    szivattyú van benne egy helyett — így a "mi táplálja ezt a szivattyút?"
    kérdésre magabiztos, de hiányos válasz érkezik. A csendes fél-igazság rosszabb,
    mint a látható hiba.

    A home a részletes előfordulás (teljes adatokkal), a references a többi lapon
    lévő rövidebb ismétlések.

    Valódi példa az OPEN100-ból, 2026-08-25-én ellenőrizve: az RCS-PU-102A jelű
    szivattyú szerepel az 5. lapon a folyamatábra részeként, és a 6. lapon is,
    ahol a "DETAIL A" részletrajz mutatja ugyanazt a gépet. Két rajzjel, egyetlen
    szivattyú.

    Az írásmód is ingadozhat: ugyanezen az 5. lapon a rajzjel felirata
    RCS-PU-102A, a lap alján lévő berendezés-jegyzékben viszont RC-P102A áll
    ugyanarra a gépre. Ez a példa viszont **lapon belüli** eltérés; azt, hogy egy
    tag laponként is másképp lenne írva, ebben az adathalmazban még nem láttuk
    igazolva. A tag_variants mező készen áll rá, ha felbukkan.
    """

    tag: str
    home: str
    references: list[str] = Field(default_factory=list)
    tag_variants: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_not_alone(self) -> IdentityGroup:
        if not self.references:
            raise ValueError(
                f"identity group for {self.tag!r} has no reference occurrences; "
                "a group needs at least two occurrences to be worth recording"
            )
        return self


class UnresolvedConnector(BaseModel):
    """Egy csatlakozó, amelyről tudjuk, hogy nem lóg — de a párját mégsem találtuk meg.

    Ez a harmadik eset a "párba került" és a "lógó" mellett, és valódi rajzokon
    elő fog fordulni: a célként megnevezett lap megvan a korpuszban, csak épp
    rajta nem található hozzáillő csatlakozó. Ennek több oka is lehet — elolvasási
    hiba, a rajzoló elfelejtette berajzolni a párját, vagy a párja nem
    "inlet/outlet" címkével van jelölve az annotációban. Egyik sem szabad, hogy
    csendben eltűnjön: ezért kap saját kategóriát ahelyett, hogy erőltetett párba
    vagy hibás "lógó" bejegyzésbe kerülne.
    """

    from_key: str
    reason: str


class SplitManifest(BaseModel):
    """Egy többlapos rajzsorozat teljes megoldókulcsa, egyetlen fájlban."""

    source: str
    sheet_files: list[str]
    connectors: list[ConnectorObservation] = Field(default_factory=list)
    connector_pairs: list[ConnectorPair] = Field(default_factory=list)
    dangling: list[DanglingReference] = Field(default_factory=list)
    unresolved: list[UnresolvedConnector] = Field(default_factory=list)
    identity_groups: list[IdentityGroup] = Field(default_factory=list)

    strategy: str | None = None
    seed: int | None = None
    source_graph_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def accounted_for(self) -> bool:
        """Igaz, ha minden csatlakozó sorsa ismert: párba került, lógó, vagy nyíltan megoldatlan.

        Csatlakozó nem tűnhet el nyomtalanul. "Ismert sorsú" nem azt jelenti, hogy
        meg is oldottuk — az unresolved lista pont azért létezik, hogy egy valódi,
        kézzel át nem ellenőrzött esetet be lehessen vallani ahelyett, hogy vagy
        kimaradna, vagy erőltetett (és ezáltal hamis) párba kerülne.
        """
        placed = {p.from_key for p in self.connector_pairs}
        placed |= {p.to_key for p in self.connector_pairs}
        placed |= {d.from_key for d in self.dangling}
        placed |= {u.from_key for u in self.unresolved}
        return placed == {c.key for c in self.connectors}
