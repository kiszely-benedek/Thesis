---
topic: Ontológia P&ID-khez — mi az, mi létezik már (DEXPI, ISO 15926, IDO, PCA RDL), mit használnak a cikkek, és hol van a valódi hiány
status: draft
related: [ADR-0002, lpg-vs-rdf.md, 10-literature/ontology-landscape.md]
date: 2026-09-08
---

# Ontológia P&ID-khez — a professzor kérdésére adott válasz háttere

A professzor 2026-09-08-án ezt kérdezte: *„Van-e ontológia, milyen ontológián dolgoznak, vagy ez a
nagyokból hiányzik (schema.org), vagy hiányzik és kell egy P&ID ontológia? Ontológia mindenképpen
kellene."* A rövid válasz: **van, több is, de egyiket sem használja senki visszakeresésre, és egyik sem
tud lapok közötti azonosságról.** Ez a jegyzet elmagyarázza, hogy ez a mondat mit jelent, és miért
pont ez a dolgozat helye. Minden tényállítás forrása a `docs/private/10-literature/ontology-landscape.md`
kutatási jegyzet (2026-09-08), ahol minden állítás mellett URL van; itt a forrásokat nem ismétlem meg.

## Miért létezik egyáltalán az ontológia fogalma?

Kezdjük a problémával. Két mérnökiroda két P&ID-t rajzol ugyanarról az üzemről. Az egyik
„centrifugálszivattyú"-nak hívja a dolgot, a másik „PU"-nak, a harmadik CAD-rendszer belső kódja
`EQ-0412`. Egy ember látja, hogy ugyanarról van szó. Egy program nem — hacsak valaki le nem írta neki,
hogy *mi micsoda*, és *mi minek az altípusa*.

Az **ontológia** ennek a leírásnak a formális, géppel olvasható változata: egy fogalomhierarchia
(„a centrifugálszivattyú egy szivattyú, a szivattyú egy berendezés") plusz a fogalmak közti
kapcsolatok típusai („egy szivattyúnak van szívó- és nyomócsonkja") plusz olyan szabályok, amelyekből
egy motor következtetni tud. Az `lpg-vs-rdf.md` jegyzetben ez volt az RDF-oldal „kódolt kontra
levezetett szabályok" pontja: az ontológia az a szótár, amelyre az RDF-hármasok hivatkoznak.

Fontos, hogy három, gyakran összekevert dolgot szétválassz:

| Fogalom | Mit ad | Példa |
|---|---|---|
| **Rajzi szabvány** | hogyan *néz ki* egy szimbólum a papíron | ISA-5.1 (műszerbetűk), ISO 10628 (folyamatábra-jelek) |
| **Információs modell** | milyen *osztályok és attribútumok* vannak, és hogyan cserélünk fájlt | DEXPI (UML + XML), CFIHOS (Excel/CSV) |
| **Ontológia** | ugyanez *formális logikával*, globális azonosítókkal, következtethetően | ISO 15926, IDO, PCA RDL, OntoCAPE (OWL) |

A professzor kérdése a harmadik sorra vonatkozik. A P&ID-világ nagy része a második sorban él.

## Mi létezik ma? — a lényeg négy tételben

### 1. DEXPI — az információs modell, amit mindenki használ, és ami *nem* ontológia

A **DEXPI** (Data Exchange in the Process Industry) az európai vegyipar által fenntartott P&ID-adatmodell.
A 2.0-s verzió 2025 októberében jelent meg, Creative Commons licenc alatt, UML-ben modellezve, saját
XML-szerializációval. A specifikáció forrásrepójában (GitLab, 225 fájl) **egyetlen OWL, RDF vagy Turtle
fájl sincs** — ezt a kutató 2026-09-08-án a GitLab API-n keresztül ellenőrizte. Tehát DEXPI = osztályok
és XML-séma, nem ontológia.

A `pyDEXPI`, amit mi használunk (ADR-0003), ezt a modellt Pydantic-osztályokként adja: 514 osztály, a
DEXPI 1.3 alapján. RDF-et vagy SPARQL-t nem ismer.

**De a DEXPI szemantikailag le van horgonyozva.** A DEXPI az ISO 15926 4. részét használja
referenciaadat-könyvtárként, és ez a pyDEXPI kódban is látszik: **105 osztály docstringje egy
RDL-IRI-re hivatkozik** (`http://data.posccaesar.org/rdl/RDS...`). A kutató egyet lekért Turtle
formátumban, és a definíció szóról szóra megegyezett a pyDEXPI docstringjével. Vagyis **a híd a mi
Pydantic-modellünk és egy élő RDF-szótár között már benne van a forráskódban, amit használunk.** Ez az
ADR-0002 RDF-oldalának a legfontosabb gyakorlati ténye.

### 2. Az ontológia-réteg: ISO 15926, IDO, PCA RDL

- **ISO 15926** — a folyamatipari üzemek teljes életciklus-adatára szóló szabványcsalád. A 8. része
  OWL/RDF megvalósítás, a 12. része OWL2 ontológia (ezek a Wikipediáról származó, nem az ISO-szövegből
  ellenőrzött állítások). A szabvány szövege fizetős; a referenciaadat-könyvtár böngészhető.
- **IDO** (Industrial Data Ontology, ISO 23726-3, korábban ISO/TR 15926-14) — W3C OWL 2 felső
  ontológia ipari eszköz- és folyamatadatokra; v4.2 FDIS 2026 áprilisában.
- **PCA RDL** (POSC Caesar Association Reference Data Library) — a konkrét berendezés-, cső- és
  műszerosztályok gyűjteménye. Két generációja van: a régi `data.posccaesar.org/rdl/RDS...` IRI-k **ma is
  Turtle-t adnak vissza**; a modern `PCA_...` könyvtár OWL 2, de gépi lekérésre **HTTP 401**-et ad
  (hitelesítés kell). Az RDL-ben 198 osztály van „(DEXPI symbol)" jelöléssel.
- **OntoCAPE** — az RWTH Aachen vegyészmérnöki ontológiája, 62 OWL-fájl, GPL licenc, **2009 óta
  nem frissül**. Történelmileg fontos, gyakorlatilag halott.
- **CFIHOS** — az olajipari átadási adatszabvány (IOGP); a referenciaadata **csak Excel és CSV**, RDF
  nincs (az IDO-kompatibilis változat egy 2024-es munkacsoporti mandátum, nem kiadás).

Tehát a professzor első kérdésére: **igen, van ontológia, komoly is** — csak nem a P&ID-rajzolás
szintjén, hanem az üzemi életciklus-adatok szintjén, és a DEXPI ehhez kapcsolódik, nem helyettesíti.

### 3. Egy OWL-DEXPI **épül** — de nem mi építjük

A dexpi.org 2026-03-23-i hírében szó szerint: a **TotalEnergies** „currently building a semantic version
of the DEXPI models", BFO-hoz (ISO 21838-2) és IDO-hoz igazítva, „still under development". Emellett az
EU-s **Arrowhead fPVN** projekt egyik munkacsomagja a DEXPI/CFIHOS/STEP szemantizálása.

Mennyire jutottak? A kutató végigolvasta az Arrowhead-kézikönyv DEXPI-fejezetét: a DEXPI
*életciklus-zónáit* és *tulajdonságmodelljét* igazították az IDO-hoz, Turtle-ben, GraphDB-ben ellenőrizve
— **egyetlen, kézzel írt szivattyú-példán**, `example.com` névterekben. A „connector" szó **egyszer sem
fordul elő** a kézikönyvben. A P&ID-*topológia* (mi mihez csatlakozik) nincs benne.

Ebből következik a dolgozat számára a legfontosabb tanulság: **„megépítjük a P&ID-ontológiát" nem
védhető szakdolgozati hozzájárulás.** Egy ipari konzorciummal versenyeznél, és ha időben nyernél is,
tekintélyben veszítenél. Amit mi csinálunk, azt *dolgozat-hatókörű leképezésnek plusz többlapos
kiterjesztésnek* kell hívni, és annak is kell lennie.

### 4. schema.org és a többi „nagy" szótár

A professzor konkrétan a schema.org-ot említette. A válasz: **nem, és tervezetten nem.** A schema.org
V30.0 (2026-03-19) 823 típust tartalmaz; a `/Pump` oldal HTTP 404-et ad; szelep, csőszakasz vagy
szabályozókör osztály nincs a teljes hierarchiában. A schema.org küldetése strukturált adat *keresőmotorok*
számára — receptek, események, termékek —, nem mérnöki tárgyak.

A többi általános szótár sem segít: a **Wikidata** ismeri a fogalmakat (szivattyú, szelep, P&ID,
szabályozókör), de nincs tag-, csonk- vagy lapközi-csatlakozó-szemantikája; a **QUDT** csak
mennyiségek és egységek (ezt viszont *használni fogjuk*, pont erre); a **SOSA/SSN** szenzorokról és
megfigyelésekről szól, berendezés és topológia nélkül; a **Brick/SAREF** épületekre való; az **IOF**
gyártásra, folyamatüzemi modul nélkül.

## Mit használnak a cikkek, amikre a dolgozat épül?

**Semmi formálisat.** Ez a második legfontosabb megállapítás, és idézetekkel áll:

- „Talking like P&IDs" (2502.18928): *„Node labels are inherited from the pyDEXPI class name and its
  parent class"* — a pyDEXPI osztálynév mint Neo4j-címke.
- ChatP&ID (2603.22528): a pyDEXPI osztályhierarchiát csomópontcímkékként kódolja; és — ez a fontos —
  **kifejezetten megfontolja az RDF/SPARQL-t, és elutasítja** az LPG javára, mert az szerintük
  „particularly well-suited for representing such attribute-rich engineering data". Ez pontosan az a
  kompromisszum, amit az ADR-0002 szerint *mérni* kell, nem feltételezni.
- A szabályalapú javítás (2502.18493): 33 szabály NetworkX + VF2 részgráf-illesztéssel, SHACL nincs.
- **Új találat:** **PIDQA** (Gupta és társai, MAKE 7(2):39, 2025. június) — **64 000 kérdés-válasz pár
  500 lapon**, Cypherrel generált alapigazsággal. Ez a terület eddigi legnagyobb P&ID-QA kiértékelése.
  A csomópontcímkék az **1-től 32-ig terjedő egész számok**. És minden kérdés **egy lapra** vonatkozik.
  Ez megemeli a kiértékelési mércét, amit el kell érnünk, de a lapközi kérdést nem érinti.

Tehát a professzor második kérdésére: **a cikkek nem dolgoznak ontológián.** A gráfcímkék
osztálynevek-stringek vagy számok. Az RDF egyszer jelenik meg az irodalomban, mint elvetett opció.

## Hol van akkor a valódi hiány? — a pontos megfogalmazás

Itt kell a legóvatosabbnak lenni, mert egy bírálónak egy mondat elég a cáfolathoz.

**Amit NEM szabad állítani:**
- „Nincs P&ID-ontológia." — Hamis: ISO 15926 / IDO, PCA RDL, OntoCAPE.
- „Mi építjük az első DEXPI-ontológiát." — Hamis: TotalEnergies, 2026-03-23.
- „Nincs szótár a lapközi csatlakozókhoz." — Hamis: a DEXPI 1.3-ban **16 off-page connector osztály**
  van, köztük a `PipeOffPageConnectorReferenceByNumber` a `referencedDrawingNumber` és
  `referencedConnectorNumber` attribútumokkal.
- „Az ISO 15926-nak nincs OWL-formája." — Hamis: 8. és 12. rész. Ami igaz, az szűkebb: ma nem
  tölthető le ingyen, teljes, betölthető OWL-csomag belőle, és a jelenlegi PCA RDL 401-et ad.

**Amit szabad, és amit a források alátámasztanak:**
1. Ma **nincs publikált, betölthető OWL/RDF/SHACL-változata a DEXPI P&ID-modellnek** (üres RDF-keresés
   a forrásrepóban; a DEXPI saját 2026-03-23-i hírei szerint *épül*).
2. **Egyetlen P&ID-digitalizálási vagy -QA cikk sem használ formális ontológiát**; a címkék pyDEXPI
   osztálynevek, kézi listák vagy egész számok.
3. **Nincs P&ID-visszakeresési alapvonal RDF/SPARQL fölött semmilyen korpuszméreten** — hiányként
   jelentve, nem lehetetlenségként.
4. **A DEXPI a lapközi folytatást csak feloldatlan string-párként fejezi ki** (rajzszám +
   csatlakozószám), és **nincs benne konstrukció arra, hogy egy tagelt elem az egyik lapon ugyanaz,
   mint a másikon**. Egy `DexpiModel` = egy rajz. Nincs rajzkészlet-tároló.

Ebből a hiány őszinte megfogalmazása:

> P&ID-ontológia **nem** hiányzik — a DEXPI (információs modellként) és az ISO 15926 / IDO
> (ontológia-rétegként) lefedi a területet, és a hivatalos OWL-DEXPI-t az ipar építi. Ami hiányzik:
> (a) bármilyen **ma betölthető** OWL/SHACL-forma a DEXPI-ből, (b) ezek bármilyen használata
> **visszakeresésre**, bármilyen méreten, és (c) bármilyen szótár vagy benchmark a **rajzok közötti
> azonosságra** — lapközi csatlakozók feloldása és tag-azonosság lapok között. Az (a) kéthetes mérnöki
> munka, és a hiteles változatot más fogja publikálni; a (c) az, ahol a hozzájárulás van, és annak az
> (a) csak eszköze.

Vedd észre: a (c) **pontosan az, amit az OPEN100-on már kézzel megcsináltál** — a 23 pár, 42 lógó és
8 feloldatlan csatlakozó a `SplitManifest`-ben *az a lapközi alapigazság, amire nincs szótár*. A
professzor ontológia-kérdése és a te augusztusi annotációs munkád ugyanarra a pontra mutat.

## Hová illik a dolgozatban? — a javasolt szótár

Ezek a kutató **ajánlásai**, nem tényei; az RDF-oldal `architect` tervezési jegyzete újra fogja
érvelni őket.

1. **Ne találjunk ki szótárt, de ne is várjunk másra.** Saját vékony névtér, *gépileg generálva* a 514
   pyDEXPI-osztályból, változatlan osztálynevekkel — így az LPG- és az RDF-tároló címkéi ugyanazok a
   stringek maradnak, és a ChatP&ID-vel való összehasonlíthatóság megmarad.
2. **Kifelé igazítás** a meglévő szótárakhoz: az osztályokat a régi PCA RDL IRI-khez
   (`rdfs:subClassOf` / `skos:exactMatch`, mert azok ma dereferálhatók, és a pyDEXPI docstringjei
   már nevezik őket), az egységeket a **QUDT**-hoz.
3. **A saját kiterjesztés kicsi, és ez a dolgozat tárgya:** kb. tíz osztály és tulajdonság —
   rajzkészlet-tároló (`hasSheet`), *feloldott* lapközi folytatás (`continuesAs`), tag-azonosság lapok
   között (`sameTaggedItemAs` + `IdentityGroup`, biztonságosabb, mint az `owl:sameAs`, amely
   korlátlanul összeolvaszt mindent), és állításonkénti eredet (melyik lap, melyik rácscella, ki
   igazolta — ez a `verified_by_human`, amit már így is vezetünk).
4. **Két mérés teszi megérdemeltté az RDF-oldal költségét**, és egyiket sem végezte el egyetlen cikk
   sem: (i) hármasszám és lekérdezési késleltetés LPG kontra RDF ugyanazon a korpuszon, 1 → 12 → ~100
   lapon; (ii) a tranzitív tag-azonosság lezártja, ami SPARQL-ben egy tulajdonságút vagy egy OWL-axióma,
   Cypherben kézzel írt bejárás. Ha a következtetés valahol nyer, itt nyer.
5. **Nem** választjuk elsődleges szótárnak: schema.org, SOSA/SSN, Brick/SAREF, IOF, OntoCAPE — a fenti
   okokból. Megfontoltként és elvetettként idézzük őket.

## Gyakori félreértések

1. **„Ontológia = adatbázisséma."** Nem. A séma azt mondja, mit *tárolhatsz*; az ontológia azt, mit
   *jelent*, és mit lehet belőle *levezetni*. A DEXPI XSD-je séma; az IDO ontológia.
2. **„Ha van ontológia, a gép érti a rajzot."** Az ontológia a szótár. Hogy a rajzon lévő folt egy
   szivattyú, azt a digitalizálás dönti el (75,46% él-mAP a valós adaton, lásd a W34 log), nem az
   ontológia.
3. **„Az RDF-hez kell ontológia, az LPG-hez nem."** Az LPG-nek is van szótára — a címkék —, csak
   implicit és lokális. A ChatP&ID pyDEXPI-osztálynevei *de facto* ontológia, formális jelentéstan nélkül.
4. **„A DEXPI nem tud lapközi csatlakozókról."** Tud — 16 osztálya van rá. Amit nem tud: *feloldani*
   őket, és kimondani, hogy két lapon lévő két elem ugyanaz.
5. **„Egy szakdolgozat megépíthet egy ontológiát."** Egy *kiterjesztést* megépíthet. A teljes
   DEXPI-ontológiát egy olajvállalat építi egy ISO-bizottsággal karöltve; ezzel nem versenyzünk.

## Ha egy dolgot olvasol el

A kutatási jegyzet 4.3-as szakaszát (`docs/private/10-literature/ontology-landscape.md`, „The honest
formulation of the gap"): hat sor, és ez az, amit a professzornak el kell mondanod. Utána a dexpi.org
2026-03-23-i hírét a TotalEnergies-bejelentésről, hogy a saját szemeddel lásd, mi ellen *nem*
versenyzünk: <https://dexpi.org/> (hírek, 2026-03-23).
