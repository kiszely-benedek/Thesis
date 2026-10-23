---
topic: A saját üzemgenerátor — hogyan lesz elágazás egy véletlen gráfban, mi a két séma-réteg, és miért rejtjük el a megoldókulcs mezőit
status: draft
related: [ADR-0007, 40-design/plant-generator.md, 40-design/splitter.md, ontologia-pid.md, adapter-minta.md, why-a-synthetic-benchmark.md]
date: 2026-09-12
---

# Az üzemgenerátor és a gráfséma

> **Frissítés 2026-09-13: változik a generátor-döntés.** A kérésedre a generálás a
> **pyDEXPI-re épül**: a kimenet egy valódi DEXPI modell lesz. Ebből jön a Proteus XML export
> (a DEXPI szabványos fájlformátuma), és a DEXPI saját berendezés-adatmezői, például egy
> szivattyú térfogatárama és tengelyteljesítménye.
>
> Ami **megmarad**: a véletlen fa, a visszaforgatás, az egységek összekötése, a
> kereszt-kapcsolat, a szelepek és a szabályozókörök. Csak az változik, hogy sima networkx
> gráf helyett pyDEXPI modellt építenek.
>
> A **0. szakasz ezért elavult.** Az átdolgozott terv elkészült (`plant-generator.md`, 2. változat,
> ADR-0007 elfogadva 2026-09-13), a pyDEXPI-s útvonalat pedig külön jegyzet magyarázza:
> `dexpi-modell-generalas.md`. Az 1–3. szakasz érvényes, a 4–5. szakasz a 09-13-i kérdéseidre válaszol.

Ez a jegyzet a `40-design/plant-generator.md` tervet magyarázza el. Minden állítás abból a
tervből vagy a már megírt kódból jön. A tervet a tervező ügynök írta 2026-09-12-én, és még
**javaslat**: az ADR-0007 `proposed` státuszú, amíg el nem fogadod.

## 0. Mit döntött a terv, egy bekezdésben

Nem a pyDEXPI generátorát használjuk, hanem **egy saját, kicsi generátort**
(`src/plantgraph/benchmark/generator.py`). Ennek három oka van:

- **Nincs seed.** A pyDEXPI generátorának nincs seed paramétere.
- **Rossz gráfforma.** Multigráfot ad, a splitter viszont egyszerű irányított gráfot vár.
- **Csak lánc lehet.** A mellékelt mintákból érvelés szerint csak lánc vagy gyűrű épülhet (ezt nem futtattuk).

A saját generátor egyetlen seeddel indított véletlenszám-generátort használ, és egyenesen a
pyDEXPI **osztályneveit** írja a csomópontokra (`CentrifugalPump`, `Tank`, `GlobeValve`...).
Így a gráf ugyanazt a "nyelvet" beszéli, mint a korábbi cikkeké. A pyDEXPI csak két helyen
marad meg: a ChatP&ID baseline-hoz (egy valódi DEXPI XML fájl beolvasása) és az RDF-szótárhoz.

A név-egyezést ellenőriztem: a tervben és az ADR-ben szereplő összes DEXPI osztálynév
létezik a pyDEXPI 1.2.0 520 osztálya között.

## 1. Hogyan lesz elágazás: a véletlen rekurzív fa

**A probléma.** Ha minden berendezés csak az előzőhöz kapcsolódik, láncot kapunk:
A → B → C → D. Egy láncon a lapokon átnyúló kérdés csak annyi, hogy "lépkedj a
szomszédos lapokon", és a splitter négy vágási stratégiája is szinte ugyanúgy vágna. Ez a
módszert nem mutatná meg, tehát kell elágazás.

**A megoldás, a lehető legegyszerűbben.** Egy egységen (unit) belül a berendezéseket
sorban vesszük fel. Mindegyik új berendezés **véletlenszerűen választ egy szülőt a már
meglévők közül**, és a szülőtől egy anyagáram (stream) fut hozzá. Ezt hívják **véletlen
rekurzív fának** (random recursive tree).

Képzeletbeli példa, **nem egy futás eredménye**, négy berendezéssel:

- 0-s berendezés: az első, nincs szülője.
- 1-es: csak a 0-s közül választhat, tehát 0 → 1.
- 2-es: a {0, 1} közül választ; mondjuk a 0-t, tehát 0 → 2. **Itt lett elágazás**: a 0-ból két ág indul.
- 3-as: a {0, 1, 2} közül választ; mondjuk az 1-et, tehát 1 → 3.

Ebből nem lánc lesz, hanem **fa**. Pár sor kód, és mégis ágazik.

**Három kiegészítés, mind egy-egy valószínűséggel:**

- **Visszaforgatás (recycle).** Egy későbbi berendezésből ág fut vissza egy korábbiba. A
  valódi üzemekben ilyen a visszaforgató ág. Ettől a gráf már nem tisztán fa.
- **Egységek összekötése.** Minden új egység egy korábbi egység egyik berendezéséből kap
  bemenő áramot. Így az egységek is fát alkotnak, és az egész üzem egyben marad.
- **Kereszt-kapcsolat (cross-link).** Egy korábbi egység berendezéséből egy későbbi egység
  valamelyik berendezésébe megy még egy áram.

**Szelepek és szabályozókörök.**

- Minden áramra 0 és egy felső korlát közötti számú szelep kerül.
- Egy berendezéshez adott valószínűséggel **szabályozókör** is tartozhat: mérő → szabályozó →
  beavatkozó → szelep. A tagek a megszokott betűket követik: F áramlás, L szint, P nyomás,
  T hőmérséklet. Például `FT-3-1` a mérő, `FIC-3-1` a szabályozó, `FV-3-1` a beavatkozó.
  Ugyanilyen betűs jelöléseket látsz az OPEN100 lapokon is (FT, PT, TE, LIT).

**Miért fontos, hogy a típus a szerkezethez kötődjön.** Lehetne még egyszerűbb: egy véletlen
gráf, a csomópontokra véletlen címkékkel. A terv ezt kifejezetten elveti. Ha a "szivattyú"
címke független attól, hol áll a csomópont a gráfban, akkor egy "mi táplálja ezt a
szivattyút?" kérdés semmit nem tesztel, csak egy címkét keres ki. Itt a berendezések az áramok
végén állnak, a szelepek az áramokon ülnek, a szabályozókörök a berendezésekhez tartoznak.
Ettől lesznek értelmes kérdések. **Ez az egyetlen pont, ahol az egyszerűség engedett a módszer
igényének**, és a terv ezt nyíltan kimondja.

**Reprodukálhatóság.** Minden véletlen döntés egyetlen `random.Random(seed)` példányon megy
át, és halmazokon soha nem járunk végig rendezetlenül. Ugyanaz a seed ugyanazt az üzemet adja.
Pontosan ugyanez a szabály a splitterben is.

## 2. A két séma-réteg

Az "ontológia" kérdésedre ez a konkrét válasz. **Kell, a lekérdezés oldalán**, és két rétegből
áll.

### Topológiai réteg: mi van összekötve mivel

Ezt adja a generátor, és ezt vágja a splitter. Négy kapcsolattípus van, a korábbi cikkek
elnevezéseivel:

| Kapcsolat | Jelentése |
|---|---|
| `send_to` | anyag áramlik innen oda (csővezeték) |
| `send_signal_to` | jel megy innen oda (műszer → szabályozó → beavatkozó) |
| `control` | a beavatkozó szabályozza a szelepet |
| `measured_by` | a berendezést ez a mérő figyeli |

### Szerkezeti réteg: mi hol van és mihez tartozik

Üzem → egység → lap tartalmazás, valamint a lapokon átnyúló kapcsolatok. Például
`continues_as`: ez a csatlakozó ott folytatódik; `same_tagged_item_as`: ez ugyanaz a
berendezés egy másik lapon. Ezek nagy része a 09-08-i ontológia-kutatásban javasolt, nagyjából
10 fogalmas **többlapos kiegészítés**. Ezt a réteget a **betöltő** (loader) építi meg a
gráfadatbázisban, a node-attribútumokból és a megoldókulcsból.

### Miért nem egyetlen réteg

Csábító lenne az egység-csomópontot is éllel bekötni a generált gráfba, hogy "ez a szivattyú
az 1-es egységhez tartozik". A terv a kódból mutatja meg, miért tönkretenné a splittert:

1. **Csoportosítás.** A splitter egy szélességi bejárással (BFS) csoportosítja a
   csomópontokat. Ha egy egység-csomópont minden elemével össze van kötve, hirtelen minden elem
   két lépésre lesz minden másiktól, és a csoportosítás értelmét veszti.
2. **Vágás.** A splitter minden élt, amely két lap között fut, **off-page connectorrá** alakít.
   A tartalmazás-élekből így értelmetlen csatlakozók lennének: "ez a szivattyú a másik lapon
   folytatódik az egységben".

Ezért az egység csak egy **attribútum** (`unit_id`) a csomópontokon, és a tartalmazás-éleket
a betöltő rakja be később. Ugyanez a szétválasztás (tartományi és lexikális kapcsolatok) a
"Talking like P&IDs" cikkben is megvan; a terv csak oda teszi, ahol a splitter elbírja.

## 3. Látható és rejtett mezők: miért nem kerül a megoldókulcs az adatbázisba

**Hasonlat.** Egy vizsgán a tanuló megkapja a feladatlapot, de a megoldókulcsot nem. Ha a
megoldókulcs véletlenül a feladatlap hátoldalára kerül, a vizsga már semmit nem mér.

A benchmarkban a "tanuló" a **keresőrendszer** és a **lapközi összekötő** (resolver): az a
komponens, amelynek ki kell találnia, melyik csatlakozó melyikkel alkot párt, és melyik
berendezés ugyanaz két lapon. Ezért a terv minden mezőt megjelöl:

- **V (visible):** látható a keresőnek. Ilyen a `tag`, az osztály, a `line_number`, a csatlakozó
  felirata.
- **G (gold):** csak a megoldókulcsban van, a vizsgált adatbázisba **soha nem kerül be**.

**A legfontosabb példa: a `node_id`.** A splitter egy duplikált berendezést a többi lapon
**ugyanazzal a `node_id`-vel** rajzol fel (`_draw_on_neighbour_sheets`). Ha a `node_id` bekerülne
az adatbázisba, a resolvernek nem kellene kitalálnia semmit: elég lenne megnéznie, hol egyezik a
`node_id`. A tag-azonosság megoldókulcsa szivárogna ki. Ezért az adatbázisban minden
előfordulás egy **átlátszatlan azonosítót** kap: a lap és a `node_id` összefűzésének SHA-1
lenyomatának első 12 hexadecimális jegyét. Ebből nem lehet visszafejteni, hogy két előfordulás
ugyanaz-e. A leképezés a megoldókulcsban marad.

### Lépésről lépésre, egy konkrét szivattyúval

Vegyünk egy szivattyút, amelynek a tagje `P-101`. A generátor belsejében ennek van egy saját
azonosítója is, mondjuk `plant0-u2-eq5`. Ez a gép **két lapra** kerül: a 3. lapra teljes
adatokkal (home), a 7. lapra csak a tag-gel (reference).

**1. Mi kerül az adatbázisba (a "feladatlap").** Minden, ami egy valódi, beolvasott rajzon is
látszana:

- a lapok;
- a csomópontok osztálya és tagje;
- a csatlakozók felirata ("folytatás a 7. lapon");
- a berendezés-táblázat értékei.

A 3. lapi és a 7. lapi szivattyú **két külön csomópont** lesz, két értelmetlennek látszó
azonosítóval, például `a3f9c21b7e04` és `91be0d4c22fa`.

**2. Mi marad kint (a "megoldókulcs").** Ez a `SplitManifest` fájlban van, az adatbázisban
nincs:

- hogy ez a két csomópont **ugyanaz a gép**;
- hogy melyik csatlakozó melyikkel alkot párt;
- az eredeti, szét nem vágott üzemgráf.

**3. Mit mérünk.** Azt, hogy a rendszer **a látható információból ki tudja-e találni** a
kapcsolatokat. Például: ugyanaz-e a 7. lapi `P-101`, mint a 3. lapi `P-101`? Egy valódi rajzon ez
sem mindig egyértelmű. Az OPEN100 5. lapján (ezt a képet te is letöltötted) a rajzon
`RCS-PU-102A` áll, a lap alján lévő táblázatban viszont `RC-P102A` ugyanarra a gépre. A
rendszernek az ilyen eltérésekkel is meg kell birkóznia.

**4. Mi történne, ha a `node_id` bekerülne.** Mindkét csomóponton ott állna a
`plant0-u2-eq5`. Egy egyszerű lekérdezés ("keresd meg azokat a csomópontokat, amelyeknek
egyforma a `node_id`-je") **100%-os** eredményt adna, anélkül hogy bármit kitalált volna. A mérés
hibátlannak mutatná a rendszert, pedig semmit nem tesztelt. Ezt hívják **szivárgásnak**
(leakage): a megoldás kiszivárog a feladatba.

**5. Bekerülnek-e végül a kapcsolatok az adatbázisba?** Igen, csak jelölve.

- A kész rendszerben, miután a resolver megtalálta a párokat, **az ő eredményei** kerülnek be
  (`asserted_by = resolver`), és azokon már lehet lekérdezni.
- Egyes kísérletekben szándékosan a helyes kapcsolatokat töltjük be (`asserted_by = oracle`),
  hogy a keresést a kapcsolatkereséstől külön mérjük.

A lényeg: **mindig tudjuk és jelöljük, honnan jön egy kapcsolat**, és a vizsgált rendszer
sosem látja a megoldókulcsot, amikor éppen azt mérjük, ki tudja-e találni.

**Egy másik rejtett mező: a `stream_kind`.** Megmondja, hogy egy áram fa-ág, visszaforgatás,
egységek közötti vagy kereszt-kapcsolat. Az elemzéshez hasznos, de a keresőnek nem szabad
látnia, mert ilyen címke egy valódi rajzon nincs.

**Ki tartatja be.** A betöltő a `schema.py` két listája alapján dönt: csak ami a látható
listán van, az kerül be. Ez kódszintű garancia, nem jóindulat.

## 4. Hol van a szivattyú? Szabályok, ontológia és a mi sémánk

Háromféle "tudás" létezik a P&ID-kről, és könnyű összekeverni őket.

| | Mit mond | Példa | Nálunk |
|---|---|---|---|
| **Tervezési és rajzolási szabályok** | hogyan kell egy üzemet megtervezni és lerajzolni | ISO 10628, PIP PIC001, a Hanford HNF-64103 ("a H betűs") | most kimarad; egy későbbi fázisban fokozatosan jön |
| **Tartalmi ontológia / információs modell** | mi egy szivattyú, milyen fajtái vannak, milyen adatai | a DEXPI osztályhierarchiája, az ISO 15926-4-hez kötve | **készen van, átvesszük** |
| **A mi sémánk** | hogyan kapcsolódnak a dolgok a gráfban, lapon belül és lapok között | `send_to`, `control`, a lap, `continues_as`, `same_tagged_item_as` | a lapközi rész **új**, ez a hozzájárulás |

A Hanford-dokumentum tehát **nem ontológia**, hanem szabálygyűjtemény arról, hogyan kell
rajzolni.

**Hol van a szivattyú?** A tartalmi ontológiában, és onnan kerül a gráfba. A pyDEXPI-ben a
`CentrifugalPump` osztály szülőlánca (ellenőrizve 2026-09-13):
`CentrifugalPump → Pump → Equipment → … → TaggedPlantItem → … → TechnicalItem`.
Magyarul: a centrifugálszivattyú egy szivattyú, a szivattyú egy berendezés, a berendezés pedig
tag-gel ellátott üzemi elem.

Saját adatmezői is vannak, például:

- `designVolumeFlowRate`: tervezett térfogatáram;
- `differentialPressure`: nyomáskülönbség;
- `designRotationalSpeed`: fordulatszám;
- `designShaftPower`: tengelyteljesítmény.

Ezek jól megfeleltethetők a rajz alján lévő berendezés-táblázat oszlopainak (az OPEN100 lapokon
CAPACITY, DISCHARGE, RPM, HP). A megfeleltetés a mi értelmezésünk, a DEXPI nem mondja ki. Az
általad letöltött OPEN100 lapokon ezek a mezők ki vannak nyomtatva, de üresek; a generátor
szintetikus értékekkel tölti ki őket.

**Mit tesz ehhez hozzá a mi sémánk?**

- **Lapon belül:** a szivattyú egy csomópont `CentrifugalPump` osztállyal és a fenti adatokkal.
  `send_to` élek kötik a szelepekhez és a tartályhoz, `measured_by` él pedig a mérőhöz.
- **Lapok között:** ha a szivattyútól induló cső átmegy egy másik lapra, a vágásnál egy
  csatlakozópár keletkezik (`continues_as`). Ha maga a szivattyú szerepel két lapon, a két
  előfordulását `same_tagged_item_as` köti össze.

Így követhető egy szivattyú kapcsolata egy másik szivattyúval sok lapon át: a lapon belüli élek
és a lapközi kapcsolatok együtt adják ki az utat.

A kérdésed tehát nagyrészt a választ is tartalmazta: a tartalmi ontológia már létezik (DEXPI),
mi a lapok közötti részt adjuk hozzá. Egy pontosítás: a topológiai réteg nem csak a lapközi
kapcsolatokról szól, a lapon belüli összeköttetéseket is leírja.

## 5. Mi a módszerünk bemenete?

Egy dokumentumtól a válaszig három szakasz vezet:

1. **Dokumentum:** PDF vagy szkennelt rajzlapok.
2. **Digitalizálás:** a szimbólumok, vonalak, feliratok és táblázatok felismerése a lapokon.
   Ebből laponként egy gráf lesz.
3. **A mi módszerünk:** a laponkénti gráfokból megtalálja a lapközi kapcsolatokat, majd
   hatékonyan keres és kérdez le a teljes dokumentumhalmazon.

**A bemenetünk a 2. szakasz kimenete**: laponkénti gráfok a látható információval (a csomópontok
osztálya és tagje, a csatlakozók felirata, a berendezés-táblázat értékei). **Nem PDF.**

A generátor és a splitter pontosan ilyen laponkénti gráfokat állít elő, ezért a 2. szakaszt
most szándékosan átugorjuk. Egyszerre egy változót vizsgálunk; ezt 2026-08-25-én döntöttük el
(`splitter.md`, 4. nyitott kérdés). A 2. szakasz hibáit az EXP-0003 szimulálja: a gráf éleinek
0–25%-át szándékosan elrontjuk, és mérjük, mennyit romlik közben a keresés.

**A PDF-ből olvasás külön kutatási terület**, és jó ötlet lehet másnak kiadni. A
Relationformer-cikk (arXiv 2411.13929) pont ezt méri: a valódi OPEN100 lapokon 75,46-os edge
mAP-t ért el.

A két munka közötti **átadási felület a laponkénti gráf formátuma**, vagyis a mi sémánk. Ha
valaki PDF-ből ilyen gráfot állít elő, a mi módszerünk azonnal futtatható rajta. Ezért fontos,
hogy a séma rögzítve legyen; a tervező ügynök ezt külön szakaszban írja le.

**A PDF-be renderelés** (a lapok és a táblázatok kirajzolása) egy későbbi fázis. A pyDEXPI
alapú modellnél ehhez van kiindulópont, mert a pyDEXPI-ben van Proteus XML exportáló modul. Azt
viszont **még nem ellenőriztük**, hogy egy generált modellből tényleg kirajzolt lap is lesz-e.
A kirajzoláshoz ugyanis a szimbólumok helyzete is kell, és egy generált modellben ez nincs
automatikusan benne.

## 6. Tévhitek

**"Saját generátor = elhagyjuk a DEXPI-t."** Nem. A csomópontok pontosan a DEXPI osztályneveit
viselik, és a kapcsolatok a korábbi cikkek neveit. Csak a pyDEXPI *futtatását* hagyjuk el a
generálásnál.

**"Véletlen fa = valószerűtlen, tehát rossz."** A valószerűség tudatosan vállalt korlát
(ADR-0007). A fának az a dolga, hogy elágazzon, és tipizált kérdésekre adjon alapot. Mindkettőt
megteszi.

**"Az ontológia egy nagy külön projekt."** Itt nem az. Négy kapcsolattípus, nagyjából 16
csomópont-osztály és egy kb. 10 fogalmas többlapos kiegészítés. A lényeg a *többlapos* rész,
mert az új.

**"Ha minden adat megvan, jobb mindent betölteni az adatbázisba."** Nem. A benchmarkban az a
lényeg, hogy a megoldókulcs **ne** legyen ott, ahol a vizsgált rendszer keres. Különben a mérés
semmit nem mér.
