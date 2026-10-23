---
topic: Miért építünk szintetikus benchmarkot — és mit csinál pontosan a splitter
status: draft
related: [ADR-0004, ADR-0001, ADR-0005, 40-design/splitter.md, open100-csatlakozo-megoldokulcs.md, pid-lapkozi-csatlakozok.md]
date: 2026-09-10
---

# Miért építünk szintetikus benchmarkot

Ez a jegyzet arról szól, mi az a `splitter`, ami most készül, és miért van rá
egyáltalán szükség. A `40-design/splitter.md` tervdokumentum erre a jegyzetre
hivatkozik.

## 1. A probléma: van egy állításunk, és nincs mivel megmérni

A dolgozat egyetlen állítást tesz:

> a legjobb visszakeresési (retrieval) stratégia a korpusz **méretének
> függvénye** — ami egyetlen rajzlapon nyer, az egy egész üzemen veszít.

Ez egy **mérhető** állítás, és pontosan ezért jó állítás. De ahhoz, hogy mérni
lehessen, kell egy adathalmaz, amelyben

- sok lap van (nem egy),
- a lapok **összefüggnek** (ugyanannak az üzemnek a részei),
- és tudjuk **előre, biztosan**, hogy melyik lap melyikhez hogyan kapcsolódik.

A harmadik pont a kritikus. Ezt hívjuk **megoldókulcsnak** (ground truth): az
ismerten helyes válaszok halmaza, amelyhez a rendszer kimenetét hasonlítjuk. Ha
nincs megoldókulcs, nincs mérés — csak vélemény arról, hogy "elég jónak tűnik".

Ilyen adathalmaz nem létezik. A szakirodalom minden P&ID-s kiértékelése egyetlen
lapon fut. A PIDQA (2025) 64 000 kérdés-válasz párt tartalmaz 500 lapról — ez a
terület eddigi legnagyobb kiértékelése —, de mind az 500 lap **külön-külön** áll,
lapok közötti kapcsolat nincs benne. Tehát a mérőeszközt magunknak kell megépíteni.
Ez a dolgozat 1. számú önálló hozzájárulása, nem mellékes előkészület.

## 2. Miért nem elég az OPEN100

Van egy valódi adathalmazunk: a PID2Graph OPEN100 részhalmaza, 12 lap egyetlen
atomerőmű-tervből, valódi lapközi csatlakozókkal. Ezt kézzel annotáltuk
(ADR-0005), háromszori független átolvasással, és **96 csatlakozóból 23 párt**
sikerült megbízhatóan összekötni; 42 az adathalmazon kívülre mutat, 8 megoldatlan.

Ez értékes — de mérőeszköznek kevés, két okból:

**Túl kicsi.** 23 pár egy pontszám, nem egy görbe. Az állításunk arról szól, mi
történik, ahogy a korpusz **nő**: 10 lap, 50 lap, 500 lap. Ehhez tetszőleges
méretű korpuszt kell tudni előállítani. 12 lapból nem lesz 500.

**Egyetlen forrás.** Egy terv, egy rajzoló ("MAJ"), egy CAD-eszköz, egy nap
(2020. 09. 01.), és rajta a felirat: *INFORMATION ONLY – NOT FOR CONSTRUCTION*.
Egy ilyen mintából nem lehet megmondani, mi általános és mi ennek az egy
tervnek a szokása.

Az OPEN100 tehát **validáció**, nem tanítóanyag: a szintetikus adaton mért
eredményt egy valódi rajzsorozaton is ellenőrizni tudjuk vele. Két különböző
szerep, és nem szabad összekeverni őket.

## 3. Mi a splitter: az inverzió ötlete

A kulcsgondolat (ADR-0004) egyszerű, és érdemes megállni nála.

Az **igazi** feladat nehéz: adott N darab beszkennelt rajzlap, találd ki, melyik
csatlakozó melyikkel alkot párt. Ehhez megoldókulcs kell, azt pedig ember
készíti, drágán és lassan — ezt éltük végig az OPEN100 96 sorával.

A splitter **megfordítja** a feladatot. Nem lapokból próbál üzemet összerakni,
hanem egy **kész, teljes üzemgráfot vág szét** lapokra:

```
teljes üzemgráf
      |
      |  particionálás: melyik node melyik lapra kerüljön
      v
  lapok halmaza
      |
      |  minden elvágott él helyére egy csatlakozópár kerül
      v
  lapok + megoldókulcs
```

És itt a lényeg: **mi magunk vágtuk el az élt, tehát pontosan tudjuk, mi volt.**
A megoldókulcs nem utólagos találgatás eredménye, hanem melléktermék. Nem kell
annotálni, nem lehet félreolvasni, és annyi lapra vágunk, amennyire akarunk.

Ezért van a `ConnectorPair` modellben a `MatchRule.SYNTHETIC` érték a
`line_number` / `grid_mutual` / `service_direction` mellett: az utóbbi három azt
mondja meg, *milyen bizonyíték alapján gyanítjuk*, hogy két csatlakozó összetartozik
egy valódi rajzon. A `SYNTHETIC` azt jelenti, hogy nem gyanítjuk — tudjuk.

## 4. A négy vágási stratégia — és miért paraméter, nem konstans

Egy gráfot sokféleképp lehet lapokra vágni, és **nem mindegy, hogyan**, mert a
vágás dönti el, hogy a benchmark hasonlít-e valódi rajzsorozatra.

A tervdokumentum négy stratégiát ír elő, mind ugyanazon felület mögött:

| Stratégia | Hogyan vág | Mit modellez |
|---|---|---|
| `flow_greedy` (alap) | a betáplálástól indul, folyásirányban halad, tele a lap → vág | ahogy a tervező valójában dolgozik |
| `modularity` | sűrűn összekötött csoportokat keres (Louvain), azok lesznek a lapok | "technológiai egységenként" |
| `utility_aware` | előbb kiemeli a közműveket (gőz, hűtővíz) külön lapokra, aztán `flow_greedy` | a sok helyről hivatkozott gyűjtőlapok |
| `random` | kiegyensúlyozott véletlen felosztás | **kontroll** — szándékosan életszerűtlen |

A `random` nem hiba, hanem a kísérlet legfontosabb eleme. Ez a **kontrollcsoport**:
ha a `random` és a `flow_greedy` ugyanazt a pontossági görbét adja, akkor az
eredmény **robusztus** — nem függ attól, hogy eltaláltuk-e a valódi rajzolási
szokásokat. Ezzel a "de a te adatod nem életszerű" kifogásra nem érvelni fogunk,
hanem **mérési eredménnyel** válaszolunk. Ha viszont eltérnek, az önmagában egy
publikálható megfigyelés: a particionálás módja számít.

Ez általános kutatásmódszertani minta, érdemes megjegyezni: **ha egy döntésedet
nem tudod megvédeni, tedd paraméterré és mérd meg.** A stratégia nem beégetett
választás, hanem a kísérlet egyik változója.

## 5. A csapda: ne illesszük a generátort az OPEN100-hoz

Ez a tervdokumentum legfontosabb figyelmeztetése, és nem magától értetődő.

Kézenfekvőnek tűnik: megmértük az OPEN100-at (laponként 181–675 node, átlag 386;
laponként 2–12 csatlakozó), állítsuk be a generátort úgy, hogy ilyet gyártson.
**Ez hiba lenne.**

Ha a generátort egyetlen rajzsorozat szokásaira hangoljuk, akkor olyan
benchmarkot kapunk, amely **azt a rendszert jutalmazza, amelyik ugyanezekre a
szokásokra épült rá** — és pont az ilyen rendszer fog elhasalni a professzor
valódi gyári dokumentumain, amelyek régebbiek, beszkenneltek, több szerzőtől,
több korszakból, kézzel firkálva, esetleg más szabvány szerint.

A helyes hozzáállás: az OPEN100 **egy megfigyelt pont**, ami bekerít egy
tartományt — nem cél, amit el kell találni. A lapméret, a csatlakozósűrűség és a
feliratozási konvenció mind **változó, tartománnyal**, és szándékosan generálunk
ezen a tartományon **kívülre** is. Ha egy későbbi komponens csak akkor működik,
ha a csatlakozó pontosan `PID 120-1 (C-1)` alakú, az **hiba, amit a benchmarknak
ki kell buktatnia**, nem elrejtenie.

Egy mérőeszköz akkor jó, ha meg tudja buktatni a saját készítőjét.

## 6. Kétféle lapközi kapcsolat — és a második a veszélyesebb

A benchmarknak mindkettőt tartalmaznia kell, mert **különböző hibát okoznak**.

| | Off-page connector | Tag-azonosság |
|---|---|---|
| Mit vágunk el | egy **csövet** — egy él kettévágva | egy **objektumot** — egy node kétszer felrajzolva |
| Hogyan áll helyre | az elvágott **élt** kötjük vissza | a duplikált **node**-okat vonjuk össze |
| Mi a jel | a partnerlapot megnevező felirat | maga a berendezés **tag**-je |
| Ha kimarad | a gráf **kettészakad** — látványos | a gráf **épnek látszik** |

A második sor a fontos. Ha egy off-page connectort nem talál meg a rendszer, a
gráf szétesik, és ez feltűnik. Ha viszont egy tag-azonosságot hagy ki — ugyanaz a
szivattyú két lapon, két különálló node-ként —, akkor a gráf **hibátlannak
látszik**, csak épp két fél szivattyú van benne egy egész helyett. A "mi táplálja
ezt a szivattyút?" kérdésre magabiztos, de hiányos válasz érkezik.

**A csendes fél-igazság rosszabb, mint a látható hiba**, mert nincs, ami
figyelmeztessen. Ezért generál a splitter szándékosan duplikált berendezéseket is
(`duplication_rate`): egy **home** előfordulás teljes adatokkal, és **reference**
előfordulások a többi lapon, csak a tag-gel — pontosan úgy, ahogy a valódi rajzok
csinálják.

És a tageket **nem** szabad triviálisan összepárosíthatóra csinálni. A valóságban
ugyanaz a gép `RC-P102A` és `RCS-PU-102A` néven is szerepel — ezt az OPEN100 5.
lapján konkrétan láttuk. A tag írásmódja is generátor-változó, külön
"csak pontos egyezés" könnyű móddal mint kontroll.

## 7. Miért hihető a megoldókulcs: a round-trip invariáns

Jogos kérdés: honnan tudjuk, hogy maga a splitter nem hibás? Ha rosszul vág, a
megoldókulcs is rossz lesz — és akkor minden rá épülő mérés értéktelen, ráadásul
**anélkül, hogy ez kiderülne**.

A válasz egy **invariáns**: olyan állítás, aminek mindig igaznak kell lennie.

```
rejoin(split(üzem)) == üzem
```

Vágd szét a gráfot lapokra, majd a megoldókulcs alapján rakd vissza. Ha az
eredmény **nem betűre azonos** az eredetivel — ugyanazok a node-ok, élek,
attribútumok —, akkor valahol hiba van a vágásban vagy a csatlakozók
beillesztésében. Ezért készül a `rejoin.py` modul, amit **kizárólag a tesztek
használnak**: nem terméki funkció, hanem bizonyíték.

> **2026-09-20, új bizonyíték.** Ez az invariáns eddig csak **4 egységnyi**, apró üzemeken futott le
> (minden round-trip teszt a `GeneratorConfig` alapértékeivel megy). Aznap megmértük nagyban is:
> **4 015 lapon, 18 048 csatlakozópárral a `rejoin(split(üzem)) == üzem` egyenlőség tartott**
> (csomópont- és élhalmazra), 3,18 másodperc alatt. Ez az első alkalom, hogy a benchmark központi
> helyességi érve nem csak játékméretben állt meg. Részletek: `30-experiments/2026-09-20-scale-smoke.md`
> (SMOKE-03).

Ez a technika **property-based testing**: nem egyetlen konkrét bemenetre
ellenőrzünk egy konkrét elvárt kimenetet, hanem egy *tulajdonságot* sok
generált bemeneten, mind a négy stratégiával. Az ilyen teszt olyan hibákat is
megtalál, amilyenre a teszt írója nem gondolt.

## 8. Reprodukálhatóság: seed és hash

Minden mért szám a `30-experiments/_results.md` táblába kerül, és egy szám ott
csak akkor ér valamit, ha valaki **újra elő tudja állítani**. Ezért van a
manifesztben `seed` és `source_graph_hash`: együtt pontosan meghatározzák, melyik
benchmark-példányon mértünk.

Ebből következik egy szigorú szabály a kódban: **ugyanaz a seed ⇒ bájtra azonos
manifeszt.** Minden véletlen döntés egyetlen, seeddel indított
véletlenszám-generátoron megy keresztül, és a halmazokon való végigjárás
sorrendje is rögzített — mert a Python halmazbejárási sorrendje futásonként
eltérhet, és ettől a "reprodukálható" teszt **néha** bukna. Az ilyen, alkalmanként
bukó teszt rosszabb, mint a mindig bukó: megtanulod figyelmen kívül hagyni.

## 9. Amit a splitter *nem* csinál

**Nem rajzol képet.** Gráfokat ad ki, nem SVG-t vagy PDF-et. Ez tudatos: a
képre rajzolás külön komponens, később.

A sorrend a felhasználó döntése volt, és jó ok van rá: **egyszerre egy változót**.
Előbb tiszta gráfon nézzük meg, működik-e a visszakeresés. Ha ott elbukik, akkor
a szkennelési zaj hozzáadása csak annyit mondana, hogy *jobban* elbukik — semmit
nem tanultunk volna. Csak ha a tiszta gráfon működik, akkor van értelme
szkennelés-szimulációt (ferdeség, zaj, JPEG-hiba) tenni alá, majd a professzor
valódi dokumentumait.

## 10. Tévhitek, amiket érdemes elkerülni

**"A szintetikus adat gyengébb, mint a valódi."** Más célra való. A szintetikus
adat **skálát és megoldókulcsot** ad, a valódi **érvényességet**. Mindkettő kell;
a dolgozat mindkettőt használja (ADR-0004 és ADR-0005).

**"Ha a generátor gyártja az adatot, akkor körkörös az érvelés."** Csak akkor
lenne az, ha a *keresőrendszer* is a generátor feltevéseire épülne. Épp ezért
paraméter minden konvenció, és ezért van `random` kontrollstratégia.

**"A megoldókulcs biztosan helyes, hiszen mi csináltuk."** Csak ha a splitter
helyes. Innen a round-trip invariáns — a megoldókulcs helyessége is **bizonyítandó
állítás**, nem adottság.

**"23 pár az OPEN100-ból túl kevés, dobjuk el."** Nem: kevés *tanításhoz és
skálázási görbéhez*, de éppen elég **validációhoz**. Ha a szintetikus adaton mért
viselkedés a 23 valódi páron is látszik, az sokat ér.
