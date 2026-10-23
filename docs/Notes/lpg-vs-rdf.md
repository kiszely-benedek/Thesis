---
topic: Tulajdonsággráf (LPG) kontra RDF/SPARQL — melyik gráfmodell mire jó, és miért gondolhatja a professzor, hogy az RDF skálázódik jobban
status: draft
related: [ADR-0002, ADR-0004, open100-csatlakozo-megoldokulcs.md, pid-lapkozi-csatlakozok.md]
date: 2026-09-06
---

# LPG kontra RDF — két gráfmodell, két gondolkodásmód

Ez a jegyzet azért készült, mert az ADR-0002 elfogadásakor (2026-09-06) azt döntöttük, hogy **mindkét
tárolót megépítjük**: a Neo4j tulajdonsággráf lesz a fő út, mellé egy vékony RDF/SPARQL réteg épül,
hogy ugyanazt a korpuszt mindkettőn ki tudjuk mérni. Ahhoz, hogy ezt a döntést a professzor előtt is
meg tudd védeni, érteni kell, mi a különbség a kettő között, és mi az a valós érv, ami az RDF mellett
szól nagy korpusznál. Az érvek mindkét oldalon igaziak; nincs "jó" és "rossz" válasz, csak
"mire jó".

## Miért létezik egyáltalán két modell?

Mindkettő ugyanarra a problémára válasz: relációs táblákban rosszul él az olyan adat, ahol a
*kapcsolatok* legalább annyira fontosak, mint a dolgok maguk. Egy P&ID pontosan ilyen: egy szivattyú
önmagában érdektelen, az érdekes az, hogy honnan szív és hová nyom, melyik szelep zárja el, melyik
műszer méri. Egy `JOIN`-okkal teli SQL-lekérdezés ezt kínosan írja le; egy gráf természetesen.

A két modell azonban két különböző közösségből nőtt ki, és ez látszik rajtuk:

- Az **RDF** (Resource Description Framework) a W3C szemantikus web kezdeményezéséből jött. A cél az
  volt, hogy *a világ bármely két adatbázisa* összeolvasztható legyen anélkül, hogy a készítőik
  valaha egyeztettek volna. Ebből következik minden tulajdonsága: globális azonosítók, szigorú,
  egyszerű alapegység, formális jelentéstan.
- Az **LPG** (Labeled Property Graph, tulajdonsággráf) adatbázis-mérnököktől jött, a Neo4j
  népszerűsítette. A cél az volt, hogy *egy alkalmazás* gráf alakú adatát kényelmesen és gyorsan
  lehessen tárolni és lekérdezni. Ebből következik a pragmatizmusa: attribútumok bárhová
  tehetők, az azonosítók lokálisak, a séma opcionális.

## Az alapgondolat

### RDF: minden állítás egy hármas

Az RDF-ben egyetlen dolog létezik: a **hármas** (triple), azaz *alany – állítmány – tárgy*.

```
<plant/rcs/RCS-PU-102A>   rdf:type            dexpi:CentrifugalPump .
<plant/rcs/RCS-PU-102A>   dexpi:tagName       "RCS-PU-102A" .
<plant/rcs/RCS-PU-102A>   dexpi:dischargesTo  <plant/rcs/line/L-PELDA> .
```

(A `RCS-PU-102A` valódi tag az OPEN100 5. lapjáról; a vezeték és a lentebbi szelep, méret csak
szemléltető helykitöltő, nem a rajzról olvasott érték.)

Három dolgot vegyél észre:

1. **Az alany és az állítmány mindig IRI** (webcím-szerű globális azonosító), a tárgy vagy IRI, vagy
   literál (szöveg, szám). Az IRI a lényeg: a `<plant/rcs/RCS-PU-102A>` a világon egyértelmű, nem
   csak *ebben* az adatbázisban. Ha egy másik dokumentumból ugyanezt az IRI-t kapod, az *ugyanaz a
   dolog*, egyeztetés nélkül.
2. **Nincs "attribútum" mint külön fogalom.** A `tagName` ugyanolyan hármas, mint a `dischargesTo`.
   Egy csomópont "tulajdonsága" egyszerűen egy hármas, amelynek a tárgya literál.
3. **Egy élnek nincs tulajdonsága.** Ha azt akarod mondani, hogy "ez a cső 150 mm-es", a cső nem
   lehet puszta él a szivattyú és a szelep között — a csőnek saját csomópontnak (IRI-nek) kell
   lennie, amire ráakasztod a méretet. Ezt hívják **reifikációnak**, és ez az RDF egyik ára: az
   attribútumokban gazdag adat sok hármasra esik szét. (Az RDF 1.2 szabványtervezet — 2026. április
   7-én W3C Candidate Recommendation — bevezeti a "triple term" fogalmát, amellyel egy hármasról
   közvetlenül lehet állítani; ez enyhíti, de nem szünteti meg a problémát.)

A lekérdező nyelv a **SPARQL**: hármasmintákat írsz, változókkal, és a motor megkeresi az illeszkedő
részgráfokat.

```sparql
SELECT ?pump ?line WHERE {
  ?pump  rdf:type           dexpi:CentrifugalPump .
  ?pump  dexpi:dischargesTo ?line .
}
```

### LPG: csomópontok és élek, mindkettőn kulcs–érték párok

A tulajdonsággráfban két dolog van: **csomópont** és **él**. Mindkettő kaphat **címkét** (típust) és
tetszőleges számú **tulajdonságot** (kulcs–érték pár). Az azonosító a motor belügye; te a
tulajdonságok alapján keresed meg a dolgokat.

```cypher
CREATE (p:Pump {tag: "RCS-PU-102A", sheet: 5})
CREATE (v:Valve {tag: "V-PELDA"})
CREATE (p)-[:PIPE {line: "L-PELDA", size_mm: 150}]->(v)   // helykitöltő értékek
```

A cső itt egyszerűen egy él, és a mérete az él tulajdonsága. Nincs reifikáció, nincs plusz
csomópont. Ez a modell "azt rajzolja, amit a tábla mutat": a P&ID-n a cső egy vonal két szimbólum
között, és a gráfban is az.

A lekérdező nyelv a **Cypher**, amely az RDF-hez hasonlóan mintaillesztő, csak ASCII-rajz szerű:

```cypher
MATCH (p:Pump)-[pipe:PIPE]->(v:Valve)
WHERE pipe.size_mm >= 150
RETURN p.tag, v.tag
```

Egy elterjedt tévhit, hogy "az RDF szabvány, a Cypher meg a Neo4j sajátja". Ez már nem igaz:
a **GQL (ISO/IEC 39075:2024)** 2024. április 17-én jelent meg, és közvetlenül a Cypherre épül — az
SQL 1987-es szabványosítása óta ez az első új ISO lekérdezőnyelv. Tehát ma *mindkét* oldal
szabványos; a szabványosság nem különböztet meg semmit. Erre számíts, ha a professzor felhozza.

## Mi az igazi különbség? Az azonosítók és a jelentéstan

Ha lehántod a szintaxist, két valódi különbség marad.

### 1. Lokális kontra globális azonosság

Ez az a pont, ahol a professzor RDF-javaslata **a te dolgozatod központi problémájára** mutat.

A dolgozat egy kb. 100 lapos dokumentumból egy ~10 dokumentumból álló üzemrészig akar skálázni.
Ehhez a lapokon külön-külön kinyert gráfokat *egyesíteni* kell. Az OPEN100-on már láttad, mit jelent
ez: a `7/75` csatlakozó a 7-es lapon és a `8/7` a 8-ason *ugyanaz a csővezeték*, és ezt a
`SIZE-ACW-211152-SPEC-HC-X` vonalszám bizonyítja (lásd `open100-csatlakozo-megoldokulcs.md`).

- **LPG-ben** az egyesítés egy *eljárás*: minden lap gráfját betöltöd, majd egy `MERGE` lépésben
  megkeresed a kulcs (tag, vonalszám) alapján egyező csomópontokat, és összevonod őket. Ez a kód a te
  felelősséged, és minden új azonossági szabály (tag-egyezés, vonalszám-egyezés, lapközi csatlakozó
  párosítás) egy újabb `MERGE`-ág.
- **RDF-ben** az egyesítés elvileg *halmazunió*: ha a 7-es és a 8-as lap gráfját ugyanazzal az
  IRI-sémával állítottad elő, akkor a két hármashalmaz egyszerű összeöntése már a helyes egyesített
  gráf. Ha pedig két *különböző* IRI ugyanazt jelöli, azt egy hármassal *állítod* (`owl:sameAs`),
  és a motor levezeti a következményeit.

Ez az az érv, amit a professzor valószínűleg a "skálázhatóság" szó alatt ért: **RDF-ben a sok
dokumentum összeolvasztása a modell részét képezi, LPG-ben a te kódod részét.**

Az érv ereje azonban egy feltételen áll: azon, hogy *előre tudod*, mi ugyanaz. Az, hogy a `7/75`
és a `8/7` egy vezeték, nem az adatmodellből derül ki, hanem abból, hogy két független
olvasás elolvasta a rajzot és megtalálta az egyező vonalszámot. Ezt a munkát az RDF **nem
végzi el helyetted** — csak *deklaratívan leírhatóvá* teszi az eredményét. A nehéz rész (a lapközi
entitásfeloldás, a dolgozat 2. hozzájárulása) mindkét modellben ugyanannyi. Ezért maradt az LPG a
fő út: a kutatási kérdés a *visszakeresés* skálázódása, és ott az összehasonlíthatóság a ChatP&ID-vel
számít.

### 2. Kódolt kontra levezetett szabályok

Az RDF-hez tartozik két, egymást kiegészítő szabványréteg:

- **RDFS / OWL** — ontológia, azaz fogalmi hierarchia és következtetési szabályok. Ha kimondod, hogy
  a `dexpi:CentrifugalPump` a `dexpi:Pump` alosztálya, akkor a "minden szivattyú" lekérdezés
  *automatikusan* megtalálja a centrifugálszivattyúkat is. LPG-ben ezt vagy két címkével oldod meg
  minden csomóponton, vagy a lekérdezésbe írod bele a hierarchiát.
- **SHACL** — alakleírás és validálás. "Egy szivattyúnak legyen pontosan egy szívó- és egy
  nyomóoldali csatlakozása" — ezt egy pár soros SHACL-alak kimondja, és a motor jelenti a
  sértéseket. LPG-ben ezt kézzel írt ellenőrző lekérdezés.

Ez az RDF valódi többlete: **a következtetés és a deklaratív validálás**, nem a lekérdezőnyelv. Az
irodalomban (2502.18493) 33 kézzel írt javítószabály van P&ID-gráfokra; ezek egy része SHACL-ben
öt sor lenne. De ugyanennek a cikknek a szabályai *gráfátírások* (bal oldal → jobb oldal), és ez nem
a SHACL erőssége, hanem inkább a Cypher `MATCH ... SET`-é. Az RDF tehát a szabálymotor *egy részét*
váltaná ki elegánsan, nem az egészet.

## Egy kidolgozott példa — ugyanaz a lapközi kapcsolat mindkét modellben

Vegyük a `7/75 ↔ 8/7` párt az OPEN100-ból: a 7-es lapról kimenő ACW (segédhűtővíz) vezeték a 8-as
lapon folytatódik, a vonalszám mindkét végén `SIZE-ACW-211152-SPEC-HC-X`.

**LPG (Cypher).** Két lap betöltése után két külön csomópontod van a vezetékre, mert a két lap
külön-külön futott át a digitalizáláson. Az egyesítést te végzed:

```cypher
MATCH (a:Line {line_number: "SIZE-ACW-211152-SPEC-HC-X", sheet: 7})
MATCH (b:Line {line_number: "SIZE-ACW-211152-SPEC-HC-X", sheet: 8})
MERGE (a)-[:CONTINUES_ON {via: "off-page connector 7/75 -> 8/7", rule: "line_number"}]->(b)
```

Itt a párosítási szabály (`rule: "line_number"`) az él tulajdonsága lett — pont úgy, ahogy a
`SplitManifest`-ben a `MatchRule` mező. Az LPG ezt kényelmesen tárolja.

**RDF (Turtle + SPARQL).** Ha az IRI-t a vonalszámból képezed, a két lap ugyanazt az IRI-t adja, és
az egyesítés magától megtörténik:

```turtle
# a 7-es lap kimenete
<plant/line/SIZE-ACW-211152-SPEC-HC-X>  rdf:type        dexpi:PipingNetworkSegment ;
                                         plant:onSheet   <plant/sheet/7> .
# a 8-as lap kimenete — ugyanaz az alany, ezért ugyanaz a csomópont
<plant/line/SIZE-ACW-211152-SPEC-HC-X>  plant:onSheet   <plant/sheet/8> .
```

Összeöntve egyetlen csomópont van, két `onSheet` hármassal. Nem kellett `MERGE`. Viszont a
"melyik szabály alapján párosítottuk" információt nem tudod az élre írni — külön csomópontot (a
párosítás mint entitás) kell csinálnod neki. Ez a reifikáció ára a gyakorlatban.

És most a csavar: mi van a `7/33 ↔ 8/54` párral, amelyet **kizárásos alapon** párosítottunk, mert
nincs egyező vonalszám? Az IRI-séma itt nem segít: a két végen nincs közös kulcs, amiből ugyanazt az
IRI-t képezhetnéd. Vagy kimondod egy `owl:sameAs` hármassal, hogy a két csatlakozó egy vezeték
— és ezzel *te* döntöttél, nem a modell —, vagy marad két külön csomópont. Vagyis a gyenge párok
esetében az RDF ugyanott áll, ahol az LPG. **Ez a példa a dolgozat egyik legjobb érve amellett, hogy
a lapközi entitásfeloldás valódi kutatási feladat, nem adatmodell-választás kérdése.**

## Hová illik a dolgozatban?

- **ADR-0002 (elfogadva 2026-09-06):** Neo4j LPG a fő tároló, mert a ChatP&ID-vel való
  összehasonlíthatóság a leggyorsabb út egy hiteles alapvonalhoz, és a dolgozat kérdése a
  visszakeresés skálázódása. Az RDF réteg *mellé* épül, korlátozott hatókörrel: betöltő a közös
  Pydantic-modellből hármasokba, egy szókészlet-leképezés (DEXPI-osztályok → ontológia, IRI-k a
  tageknek), és egy SPARQL-alapú visszakeresési stratégia ugyanazon interfész mögött, mint az LPG
  stratégiák.
- **Mit mérünk vele?** Kettőt. (a) Ugyanazon a több lapos korpuszon jobban skálázódik-e a
  SPARQL-alapú visszakeresés, mint a Cypher-alapú — ez a professzor sejtése, kísérletté alakítva.
  (b) Mennyi az RDF hármasszám-többlete az attribútumokban gazdag P&ID-adaton — ezt a szemantikus
  web irodalma rendre *feltételezi* elhanyagolhatónak, mi *megmérjük*.
- **Hogyan fér el egy tárolóban?** A Neo4j **n10s (neosemantics)** bővítménye RDF-et importál és
  exportál, ontológiát tölt be és SHACL-validálást futtat a Neo4j-en belül. Így a "mindkettő" nem
  feltétlenül két adatbázis. Ára: az n10s *Neo4j Labs* projekt, nem a fő termék, és csak saját
  gépen futó Neo4j-hez van (Aurára nem). Ezért ez tervezési jegyzet kérdése, nem az ADR dönti el.
- **Leállítási feltétel:** ha az RDF betöltő és a SPARQL stratégia a 3. fázis végéig nem fut a
  szintetikus több lapos benchmarkon, az RDF ág megszűnik. A kereszteződési pont mérése soha nem
  vár rá.

## Gyakori félreértések

1. **"Az RDF szabvány, a Cypher nem."** — Elavult; a GQL 2024 óta ISO-szabvány, és a Cypherre
   épül. Lásd fent.
2. **"Az RDF automatikusan összeköti a dokumentumaimat."** — Csak akkor, ha az IRI-k már egyeznek.
   Az egyezés megállapítása (entitásfeloldás) ugyanannyi munka mindkét modellben; az RDF az
   *eredményt* teszi deklaratívvá.
3. **"Az RDF lassú, az LPG gyors."** — Így általánosságban nem igaz és nem is hamis; tárolótól,
   lekérdezéstől és adattól függ. A dolgozatban ezt *mérni* fogjuk, nem állítani. Semmilyen számot ne
   írj le erről, amit nem magad mértél vagy nem egy elolvasott cikkből idézel.
4. **"Az ontológia csak elmélet."** — A DEXPI szabvány maga egy információs modell osztályhierarchiával;
   az, hogy egy `CentrifugalPump` egy `Pump`, már benne van. Az RDF ezt közvetlenül tudja használni,
   az LPG-ben te másolod címkékbe.
5. **"Ha egyszer választottunk, kész."** — Az ADR-0002 kimondja, mikor kell újragondolni: ha a lapközi
   entitásfeloldáshoz valódi következtetés kell (tranzitív tag-azonosság, altípus-következtetés), az
   pont az OWL terepe, és a kézzel írt Cypher ott csúfulna el.

## Ha egy dolgot olvasol el

A W3C SPARQL 1.1 lekérdezőnyelv-ajánlásának bevezető fejezete és az első két példája:
<https://www.w3.org/TR/sparql11-query/> — utána a Neo4j Cypher kézikönyv `MATCH` fejezete ugyanerre
a problémára ugyanezt a mintaillesztő gondolkodást mutatja, csak más ruhában. Aki a kettőt egymás
mellett olvassa, az érti, hogy a különbség nem a lekérdezőnyelvben van.
