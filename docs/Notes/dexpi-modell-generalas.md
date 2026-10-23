---
topic: Hogyan épít a generátor valódi DEXPI modellt, hogyan lesz belőle gráf, és mit mértünk közben
status: draft
related: [ADR-0007, ADR-0003, 40-design/plant-generator.md, uzemgenerator-es-grafsema.md, pydexpi-szintetikus-generator.md, adapter-minta.md]
date: 2026-09-13
---

# Valódi DEXPI modell a generátorból

Ez a jegyzet a `40-design/plant-generator.md` **2. változatát** magyarázza. Ezt a változatot a
2026-09-13-i döntésed indította el: a generátor kimenete legyen valódi pyDEXPI modell. A számok a
tervező ügynök 2026-09-13-i prototípus-futásaiból jönnek. A prototípus a pyDEXPI 1.2.0-t és Python 3.13-at
használta, és nem a repóban, hanem egy ideiglenes mappában futott. Ahol valami becslés, ott ezt kiírom.

A régi jegyzet (`uzemgenerator-es-grafsema.md`) 1–3. szakasza továbbra is érvényes. A véletlen fa, a két
séma-réteg és a látható/rejtett mezők szabálya **nem változott**. Csak az változott, hogy **mit épít** a
generátor.

## 0. A döntés egy bekezdésben

A generátor ugyanazokat a véletlen döntéseket hozza, mint eddig: fa, visszaforgatás, egységek közti áram,
kereszt-kapcsolat, szelepek, szabályozókörök. Ezekből azonban nem sima networkx gráfot rak össze, hanem
**pyDEXPI objektumokat**: szivattyút, tartályt, csővezetéket, szabályozókört. Ez a DEXPI modell az egyetlen
"igazság". A splitter gráfját **ebből számoljuk ki**, pontosan azon az úton, amelyet a korábbi cikkek is
jártak: DEXPI → pyDEXPI → gráf. A tervben ez a **H1** változat.

## 1. Mi az a `DexpiModel`?

Egy **objektumfa**. A gyökere a `DexpiModel`, alatta a `ConceptualModel`, alatta pedig listák:
berendezések, csőrendszerek, műszer-funkciók, üzemszerkezet.

A DEXPI két fajta kapcsolatot különböztet meg. Ez a jegyzet legfontosabb fogalma:

| Fajta | Jelentése | Példa |
|---|---|---|
| **composition** (tartalmazás) | "része nekem" — ha én megszűnök, ő is | a szivattyú **csonkjai** (`nozzles`) a szivattyú részei |
| **reference** (hivatkozás) | "rámutatok, de nem vagyok a gazdája" | a szivattyú `parentStructure`-je az **1-es egységre** mutat |

Egy szivattyú a prototípusból, egyszerűsítve:

```
CentrifugalPump  id = "plant0-u1-eq2"
  tagName = "P-1-1"
  designShaftPower = 202.8 kW        ← adatmező (data attribute)
  parentStructure → PlantSection "1" ← reference
  nozzles = [N1, N2, N3]             ← composition
```

## 2. Hogyan lesz egy áramból DEXPI?

A régi generátorban egy áram egyetlen él volt: `P-1-1 → V-2-1`. A DEXPI-ben egy csővezetéknek több része van,
mert a szabvány a valódi csövet írja le:

```
szivattyú ─ csonk N2 ─ Pipe ─ GlobeValve GV-1-1 ─ Pipe ─ csonk N1 ─ tartály
            └──────────── PipingNetworkSegment ─────────────┘
            └──────────── PipingNetworkSystem, lineNumber = "PL-2" ────┘
```

- **Nozzle (csonk):** a berendezésen az a pont, ahová a cső csatlakozik. Minden áram-véghez új csonkot adunk.
- **Pipe:** egy csődarab két elem között.
- **PipingNetworkSegment:** a csődarabok és a szelepek sorban.
- **PipingNetworkSystem:** a teljes vonal. Ez viseli a **vonalszámot** (`lineNumber`) és a közeg kódját (`fluidCode`).

Ezeket a pyDEXPI saját segédfüggvényével rakjuk össze (`piping_toolkit.construct_new_segment`). Nem
magunk találjuk ki, hogyan kell egy szegmenst helyesen összekötni.

## 3. Szabályozókör a DEXPI-ben

Egy szintszabályozó kör (L = level, szint) öt DEXPI szereplőből áll:

| DEXPI osztály | Szerepe | Tag a prototípusban |
|---|---|---|
| `ProcessSignalGeneratingFunction` | a **mérő** (távadó) | `LT-1-1` |
| `ProcessInstrumentationFunction` | a **szabályozó** | `LIC-1-1` |
| `ActuatingFunction` | a **beavatkozó** | `LV-1-1` |
| `MeasuringLineFunction`, `SignalLineFunction` | a jelvezetékek köztük | — |
| `ActuatingSystem` + `OperatedValveReference` | "ez a beavatkozó **ezt a szelepet** mozgatja" | — |

**Egy csapda, amit a prototípus talált.** A mérő azt is megmondja, *hol mér* (`sensingLocation`). A DEXPI
szerint ez nem lehet maga a tartály, csak egy **csonk**, egy csődarab vagy egy szegmens. Először kézenfekvő
lett volna arra a csonkra tenni, ahol a cső is csatlakozik. Kipróbáltuk, és **eltűnt a cső és a mérés is** a
végső gráfból. Ennek oka: a pyDEXPI egyszerűsítő lépése csak akkor "varrja át" a csonkot, ha pontosan két
kapcsolata van, és itt három volt. A megoldás: **a mérő saját csonkot kap**.

## 4. Két fájlformátum — és egy meglepetés

| Formátum | Mi ez | Mit tud a pyDEXPI 1.2.0 |
|---|---|---|
| **Proteus XML** | a DEXPI szabványos fájlformátuma, ezt olvassák a mérnöki szoftverek | **beolvasni** mindent tud; **kiírni csak a berendezéseket** |
| **pyDEXPI JSON** | a pyDEXPI saját mentési formátuma | oda-vissza **veszteség nélkül** |

A meglepetés: a Proteus kiíró (`PlantModelExporter`) a pyDEXPI 1.2.0-ban **csak berendezést** ír ki. Nem ír ki
csővezetéket, szabályozókört vagy egységet. A prototípusban a kis modell XML-je 3 berendezést tartalmazott.
Visszaolvasva a gráfnak **0 éle** volt, a szivattyú adatai viszont megmaradtak. A GitHubon lévő legfrissebb
kód is ugyanígy működik (2026-09-13-án megnéztem).

Ezért a terv javaslata:
- a teljes, veszteségmentes mentés **pyDEXPI JSON** legyen;
- a Proteus fájl neve mondja ki, hogy csak berendezést tartalmaz (`plant.equipment.proteus.xml`);
- teljes Proteus kiírót akkor érdemes írni, ha a rajzolási fázisnak ténylegesen szüksége lesz rá. Ez döntés
  a te kezedben.

## 5. Modellből gráf: három lépés

```
DexpiModel ──1──▶ teljes gráf ──2──▶ fogalmi gráf ──3──▶ a mi sémánk szerinti DiGraph ──▶ splitter
          (GraphLoader)        (build_conceptual_graph)   (adapter)
```

1. **Teljes gráf.** Minden DEXPI objektum csomópont, minden composition és reference él. A kis modellnél ez
   36 csomópont és 70 él.
2. **Fogalmi (conceptual) gráf.** Ez a pyDEXPI saját egyszerűsítése, ugyanaz a szint, amelyen a ChatP&ID
   0.91-es eredménye született. Eltűnnek a csonkok, csövek és szegmensek; a szelep két berendezés közé kerül.
   A kis modellnél 11 csomópont és 17 él marad.
3. **Adapter.** Átnevezi az éleket a korábbi cikkek neveire, és kitölti a mezőinket. Ez a lépés azért kell,
   mert **a pyDEXPI nem a cikkekben szereplő neveket adja**:

| A pyDEXPI éle a fogalmi gráfban | Nálunk |
|---|---|
| `Pipe` | `send_to` (anyag áramlik) |
| `MeasuringLineFunction`, `SignalLineFunction` | `send_signal_to` (jel megy) |
| `OperatedValveReference` | `control` (a beavatkozó a szelepet mozgatja) |
| `sensingLocation` (mérő → tartály) | `measured_by`, **megfordítva** (tartály → mérő) |
| `parentStructure` (tartály → 1-es egység) | nem él, hanem `unit_id = "1"` mező |

Egy apróság, amit érdemes megjegyezni: **a szelepnek a DEXPI-ben nincs egysége** (`parentStructure`). Az
adapter a szelepet annak a berendezésnek az egységébe teszi, **ahonnan az áram jön**. A generátor is pontosan
ezt a szabályt követi.

## 6. Miért volt lassú, és hogyan lett gyors

**A mért tény.** A pyDEXPI gyári `GraphLoader`-e 250 egységnél (1380 berendezés, 14 598 DEXPI objektum)
**140 másodpercig** futott. 50 egységnél 4,4 másodperc volt. Az objektumok száma 5,2-szeresére nőtt, az idő
viszont 28,6-szorosára.

**Mi ez?** **Négyzetes** futásidő: kétszer annyi objektum négyszer annyi időbe kerül.

**Hasonlat.** Egy portás egy papírlistán tartja számon, ki van már bent. Minden érkezőnél végigolvassa az
egész listát. Tíz vendégnél ez gyors. Tízezer vendégnél minden új érkező tízezer sor olvasásába kerül, és az
este elmegy vele. A pyDEXPI kódja pontosan ezt teszi: egy **listában** keresi, látta-e már az objektumot
(`obj not in list`).

**A javítás.** A portás papírlista helyett **névsoros kartotékot** használ: egy halmazt, amelyben egy lépés
megnézni, bent van-e valaki. Ez egy apró alosztály (`LinearGraphLoader`), a gráfot pedig továbbra is a pyDEXPI
saját kódja építi. Két dolgot mértünk vele:
- a gyári és a javított változat **pontosan ugyanazt a gráfot** adja (5 és 50 egységnél ellenőrizve, a
  csomópontok sorrendjéig);
- **1000 egységnél** (5470 berendezés) a teljes út a seedtől a kész gráfig **15,1 másodperc**.

**Becslés, nem mérés:** a gyári változat 1000 egységnél nagyjából 37 percig futna.

## 7. Reprodukálhatóság: az azonosítók csapdája

A pyDEXPI minden objektumnak **véletlen azonosítót** ad (uuid), ha nem adunk meg sajátot. Ha csak egyet is
elfelejtünk, két futás két különböző modellt ad, és a "ugyanaz a seed, ugyanaz az eredmény" ígéret megdől.

Ezért a generátor **minden objektumnak kiírja az azonosítóját**. A szivattyú azonosítója például
`plant0-u1-eq2`, és ez egyben a gráfbeli csomópont-azonosító is.

Mértük: ugyanaz a seed háromszor, háromféle `PYTHONHASHSEED` beállítással (ez a Python belső
véletlenszerűsége). A JSON fájl mindháromszor **bájtra azonos** volt, és a gráf is ugyanaz lett. Egyetlen dolog
változott: az élek **beszúrási sorrendje**. Ezért a terv előírja, hogy az adapter mindig rendezett sorrendben
szúrja be az éleket.

**Ezért nem a pyDEXPI saját generátorát használjuk** (H2). Az minden mintát lemásol, és a másolásnál a pyDEXPI
**új véletlen azonosítót** ad minden objektumnak. Ezt is kipróbáltuk: egy `fixed-id` azonosítójú tartály
másolata uuid-t kapott. Seeddel ez nem javítható.

## 8. Berendezés-adattábla

A valódi lapok alján táblázat áll. Az OPEN100-on például egy szivattyúnál: SERVICE / CAPACITY / DISCHARGE /
RPM / HP. A DEXPI-nek vannak ilyen **adatmezői**. Azt, hogy melyik mező melyik oszlopnak felel meg, **mi
értelmezzük**; a DEXPI ezt nem mondja ki:

| OPEN100 oszlop | DEXPI mező a szivattyún | Egység a generátorban |
|---|---|---|
| SERVICE | `equipmentDescription` | szöveg |
| CAPACITY | `designVolumeFlowRate` | m3/h |
| DISCHARGE | `differentialPressure` (értelmezés; nyitott kérdés) | bar |
| RPM | `designRotationalSpeed` | min-1 |
| HP | `designShaftPower` | kW |

**Miért szám + egység.** A `GraphLoader` az értéket szövegként adja: `"202.8 kW"`. Szövegen nem lehet azt
kérdezni, hogy nagyobb-e 50-nél. Ezért az adapter két mezőt ír: `designShaftPower = 202.8` (szám) és
`designShaftPower_unit = "kW"`. Ettől működik egy ilyen lekérdezés:

```
MATCH (t:Tank {tag: "TK-1-1"})-[:send_to*]->(p:CentrifugalPump)
WHERE p.designShaftPower > 50
RETURN p.tag
```

Magyarul: "melyik szivattyú van a TK-1-1 tartály után, 50 kW-nál nagyobb tengelyteljesítménnyel?"

**Az értékek önkényesek.** Minden mezőnek egy táblázatban deklarált tartománya van (például 0,5–500 kW), és
a terv kimondja, hogy ezek **nem valószerű értékek**. A szabályokon alapuló valószerűség egy későbbi fázis.

**Home és reference.** Az adattábla csak a berendezés "otthoni" lapján szerepel. A többi lapon a berendezésnek
csak a tagje és az osztálya látszik. A splitter ezt már most is így csinálja.

## 9. A módszer bemenete: mit kell átadnia egy jövőbeli digitalizáló projektnek

A keresőrendszer **soha nem látja** a teljes üzemgráfot, a DEXPI modellt vagy a megoldókulcsot. Csak
**laponkénti gráfokat** kap. Ha később valaki PDF rajzokból olvassa vissza a lapokat, neki pontosan ilyen
laponkénti gráfokat kell átadnia. A terv §11-e ezt szerződésként rögzíti:
- **kötelező:** osztály, tag, reláció, és a csatlakozókon a partnerlap száma;
- **ajánlott:** vonalszám, egység, adattábla;
- **tilos:** bármi, ami a megoldókulcsból jön, például a lapokon átívelő közös azonosító.

## 10. Tévhitek

**"A Proteus XML export a teljes modellt kiírja."** A pyDEXPI 1.2.0-ban nem. Csak a berendezéseket írja ki.
Beolvasni viszont mindent tud.

**"A pyDEXPI `send_to` éleket ad, ahogy a cikk írja."** Nem. A 1.2.0 `Pipe`, `MeasuringLineFunction` és
hasonló címkéket ad; a cikkbeli neveket a mi adapterünk rendeli hozzájuk. Egy nyilvános DEXPI példafájlon is
ezt láttuk.

**"Ha a pyDEXPI lassú, akkor a DEXPI út nem skálázódik."** A lassúságot egyetlen rossz adatszerkezet okozta.
Javítva 1000 egység 15 másodperc. Ha mégis túl lassú lenne, a terv előre kimondja, mikor térünk vissza a
networkx generátorhoz (H3): ha a legnagyobb üzem átalakítása 10 percnél tovább tart.

**"Ugyanaz a seed mindig ugyanazt adja."** Csak akkor, ha minden DEXPI objektum kézzel megadott azonosítót
kap, és az élek rendezett sorrendben kerülnek a gráfba. Mindkettőre teszt van a tervben.

**"Python 3.10-en is megy."** A pyDEXPI 1.2.0 legalább Python 3.12-t kér. 3.10-en a `uv` nem is telepíti,
ezért a projekt beállítását emelni kell. Ez nyitott kérdés neked.
