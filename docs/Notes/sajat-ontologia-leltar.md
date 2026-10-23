---
téma: ontológia
kérdés: mit építünk pontosan, és mihez kötjük?
kiváltó ok: a professzor 2026-09-20-i megjegyzése (a felhasználó közvetítésével)
forrás: docs/private/10-literature/ontology-landscape.md (ellenőrizve 2026-09-08) + a mai kód
---

# A saját ontológiánk leltára — mit építünk, és mihez kötjük

## Miért készült ez a jegyzet

A professzor azt mondta: **„talán túlzás (overkill) ontológiát használni a lapok összekötésére vagy
hierarchiába szervezésére."** Erre nem lehet tisztességesen válaszolni addig, amíg nincs egy helyen
leírva, hogy *mi is pontosan az, amit „ontológiaként" építünk*, és hogy ebből mennyi érinti a lapok
összekötését.

Ez a jegyzet ezt a leltárt adja. Nem ismétli meg az `ontologia-pid.md`-t (az arról szól, *mi az*
ontológia, és mi létezik a világban); ez arról szól, hogy **a mi projektünkben mi épül, tételesen, és
minden egyes terminus mihez kapcsolódik kifelé.**

---

## A rövid válasz, három mondatban

1. **A lapok összekötéséhez nem építünk ontológiát, és soha nem is kellett.** A lapközi kapcsolat ma
   négy közönséges gráf-fogalom a `schema.py`-ban, és már meg van írva — lásd a 4. szakaszt.
2. **Az „ontológia" nálunk egy külön, körülhatárolt dolog:** az RDF-oldal szótára, ami az ADR-0002
   összehasonlító ágához kell (LPG kontra RDF), és aminek **saját leállítási feltétele van** a
   3. fázis végén.
3. Tehát a professzornak **igaza van** abban, hogy ontológiával összekötni a lapokat túlzás lenne —
   és mi nem is azt csináljuk. A nyitott kérdés csak az, hogy az RDF-ág *egyáltalán* megéri-e; ez
   viszont már el van döntve (ADR-0002), és méréshez van kötve, nem hithez.

---

## 1. A három réteg — mit veszünk át, és mit írunk mi

Semmit nem találunk ki, amire már van szótár. Három rétegben dolgozunk
(`ontology-landscape.md` R1, ellenőrizve 2026-09-08):

| Réteg | Mit használunk | Miért éppen azt | Ki írja |
|---|---|---|---|
| Berendezés-, cső- és műszer-osztályok jelentése | **PCA RDL** régi IRI-k (`http://data.posccaesar.org/rdl/RDS...`), `rdfs:subClassOf` / `skos:exactMatch` kötéssel | 105 pyDEXPI docstring **már most is** ezeket az IRI-ket nevezi meg, és közülük legalább 87 ma is letölthető; a DEXPI saját definíciói szó szerint innen származnak | átvesszük |
| Mértékegységek és mennyiségfajták | **QUDT** (`http://qudt.org/vocab/unit/`) | a DEXPI-tulajdonságok az IDO-igazításban QUDT-tal vannak típusozva | átvesszük |
| Minden DEXPI-specifikus, aminek nincs külső megfelelője (szerkezet, portok, lapközi csatlakozók, lap-metaadat) | **saját, vékony névtér**, pl. `https://<szakdolgozat>/ns/dexpi#` | nincs publikált DEXPI OWL, amire rá lehetne kötni (2026-09-08-i állapot) | **mi** |

**A lényeg:** a harmadik sorban is csak azért írunk saját nevet, mert nincs mihez kötni. Amint a
TotalEnergies DEXPI-ontológiája megjelenik, ahhoz igazodunk, nem versenyzünk vele.

---

## 2. A nagy rész, amit *nem kézzel* írunk

A saját névtér törzse **gépileg generálódik**, nem kézzel (`ontology-landscape.md` R2):

- a pyDEXPI **514 osztálya** → `owl:Class`;
- a pydantic mezők `json_schema_extra`-jában már meglévő `attribute_category` jelölők
  (`"composition"`, `"reference"`, `"data"`) → objektum-tulajdonság kontra adat-tulajdonság;
- a docstringekbe ágyazott `data.posccaesar.org/rdl/RDS...` IRI-k → igazítási axiómák.

Ez **ugyanaz a transzformáció, amit a ChatP&ID végez LPG-címkékre**, csak más kimeneti formátumba.
Ezért marad a két tároló összehasonlítható: ugyanazok a stringek a címkék mindkét oldalon.

Munka szempontjából ez egy szkript, nem egy ontológia-tervezési projekt. **Ez a rész nem az, amire a
professzor „overkill"-t mondott**, és nem is érinti a lapokat.

---

## 3. A saját kiterjesztés — három tétel, tételesen

Ez az a **három** dolog, amit a DEXPI **nem** tud kifejezni és nekünk kell leírnunk
(`ontology-landscape.md` R3; a DEXPI-oldali hiány a generált osztálymodellből ellenőrizve). Eredetileg
négy volt — **az R3.4-et (állításonkénti eredet) a felhasználó 2026-09-20-án elvetette.** Mindegyiknél odaírtam, **mihez kötjük kifelé**, és
hogy **érinti-e a professzor kérdését**:

| # | Mit írunk | Miért kell | Mihez kötjük | A professzor kérdését érinti? |
|---|---|---|---|---|
| R3.1 | **rajzkészlet-tároló** + `hasSheet` | egy `DexpiModel` = **egy rajz**; nincs fogalom „a rajzok halmazára" | semmihez — nincs külső megfelelője | **IGEN — ez a „hierarchia"** |
| R3.2 | **feloldott** lapközi folytatás (`continuesAs`) | a DEXPI csak a *feloldatlan* alakot adja: `referencedDrawingNumber` + `referencedConnectorNumber`, azaz két string | a DEXPI 16 off-page connector osztályára épül rá | **IGEN — ez az „összekötés"** |
| R3.3 | tag-azonosság lapok között (`sameTaggedItemAs` + `IdentityGroup`) | a DEXPI nem tudja kimondani, hogy a 3. lapon lévő P-101 ugyanaz, mint a 7. lapon lévő | `owl:sameAs` **helyett** saját tulajdonság (az `owl:sameAs` korlátlanul összeolvasztana minden tulajdonságot) | részben |
| ~~R3.4~~ | ~~állításonkénti eredet~~ **ELVETVE 2026-09-20 (felhasználó): nem kell.** A `verified_by_human` mező az OPEN100-annotációban ettől még megmarad — az egy CSV-oszlop, nem ontológia-terminus. | — | — | nem |

**Ez összesen néhány osztály és tulajdonság** (a korábbi „kb. tíz” becslés még négy tételre vonatkozott). Fontos, hogyan nevezzük: **„többlapos kiterjesztés a
DEXPI-hez"**, soha nem „egy P&ID-ontológia". A második állítást egy bíráló egyetlen mondattal
megcáfolja (TotalEnergies, 2026-03-23).

---

## 4. A döntő rész: ebből mi van **már kész, ontológia nélkül**

Itt a válasz a professzor kérdésére. A fenti három terminusból **a kettő, amit ő szóvá tett, már
létezik a kódban, közönséges gráf-fogalomként** — `src/plantgraph/graph/schema.py`:

| Ontológia-beszéd (R3) | Ami a kódban van ma | Hol |
|---|---|---|
| rajzkészlet-tároló, `hasSheet` | `NodeClass.DRAWING_SET`, `NodeClass.SHEET`, `Relation.HAS_SHEET`, `Relation.IS_DRAWN_ON` | `schema.py`, a 20 osztály és 9 reláció része |
| `continuesAs` | `Relation.CONTINUES_AS` | ugyanott |
| `sameTaggedItemAs` | `Relation.SAME_TAGGED_ITEM_AS` | ugyanott |
| a lapközi alapigazság maga | `ConnectorPair`, `OffPageConnector`, `IdentityGroup`, `SplitManifest` | `src/plantgraph/benchmark/models.py` |

Vagyis: **a lapok össze vannak kötve, és hierarchiába vannak szervezve, most, ontológia nélkül.**
Négy enum-tag és néhány Pydantic-osztály. Ez nem „ontológiát használni a lapok összekötésére" — ez
egyszerűen a gráf sémája, pontosan úgy, ahogy a professzor mondja: *csak kössük össze őket.*

> **Ha az LPG kontra RDF különbség maga nem világos** (felhasználói kérdés, 2026-09-20): ezt a
> `docs/Notes/lpg-vs-rdf.md` magyarázza el 236 sorban — mi a hármas, mi a címkézett gráf, és van benne
> egy **kidolgozott példa: ugyanaz a lapközi kapcsolat mindkét modellben felírva** (a jegyzet
> „Egy kidolgozott példa" szakasza). Az alábbi bekezdés megértéséhez az a jegyzet az előfeltétel.

**Mi az, amit az ontológia ezen felül adna?** Egyetlen dolog: formális jelentéstan, amiből a tároló
*következtetni* tud. A konkrét példa (`ontology-landscape.md` R4-ii):

- **LPG/Cypher:** a tranzitív tag-azonosság („mely rajzjelek tartoznak ugyanahhoz a fizikai
  szivattyúhoz, tetszőleges hosszú láncon át") kézzel írt bejárás.
- **RDF/SPARQL:** ugyanez **egy tulajdonságút vagy egy OWL-axióma**.

Ha a következtetés valahol nyer, itt nyer. **Ez egy mérés, nem egy hitvallás** — és pontosan ez az,
amit az ADR-0002 a döntés feltételéül szabott.

---

## 5. Akkor most overkill vagy nem?

Bontsuk szét, mert a kérdés két különböző dolgot fed:

**(a) „Ontológia kell ahhoz, hogy összekössük a lapokat?"**
**Nem, és nem is használunk hozzá.** Lásd a 4. szakaszt: négy sémabeli reláció, már megírva. Itt a
professzornak teljesen igaza van, és nincs mit módosítani — a kód már az ő álláspontját követi.

**(b) „Megéri-e egyáltalán RDF-ontológiát építeni a projektben?"**
Ez az ADR-0002 kérdése, és **már el van döntve**: az LPG az elsődleges tároló, az RDF-oldal
**mellette** épül, **korlátozottan**, és a 3. fázis végén leállítási feltétel dönt a sorsáról. Ami
mellette szól, két *mérhető* dolog, amit egyetlen cikk sem végzett el:

1. hármasszám és lekérdezési késleltetés ugyanazon a korpuszon, 1 → 12 → ~100 lapon;
2. a tranzitív tag-azonosság lezártja (a fenti SPARQL kontra Cypher példa).

**Amit érdemes a professzornak visszamondani:** „A lapokat nem ontológiával kötjük össze — az négy
reláció a gráfsémában, és már kész. Az ontológia nálunk csak az RDF-összehasonlító ág szótára,
aminek saját leállítási feltétele van. Ha az ág megbukik a mérésen, elesik, és a lapközi
összekötésből semmi nem vész el."

---

## 6. Ami ettől még nyitva marad

- **Az RDF-oldal `architect` tervezési jegyzete még nincs megírva** (ADR-0002 következménye). Az
  `ontology-landscape.md` R1–R6 pontjai kifejezetten **ajánlások, nem tények**, és annak a jegyzetnek
  újra kell érvelnie őket.
- **Felhasználói döntés, 2026-09-20: marad minden úgy, ahogy van** („keep it as it is”), ezért az
  ADR-0002 változatlan, és az RDF-ág sorsát továbbra is a 3. fázis végi leállítási feltétel dönti el,
  nem egy mostani döntés.
- **Nem tudom, a professzor a (b) kérdésre is gondolt-e**, vagy csak az (a)-ra. Ha az egész RDF-ágat
  túlzásnak tartja, az egy ADR-0002-t felülíró döntés, nem egy jegyzet-módosítás — szólj, és megírom
  az ADR-t, de a *te* professzorod indoklásával, nem az én rekonstrukciómmal.
- A PCA RDL jelenlegi végpontja **HTTP 401**, ezért a hivatkozott RDL-részhalmazt helyben kell
  tárolnunk, ha az igazítás megmarad.

---

## Ha egy dolgot olvasol el

A **4. szakasz táblázatát**. Az mutatja meg, hogy a professzor aggálya és a kód között nincs
ellentét: amit ő „overkill"-nek nevezne, azt nem csináljuk, és amit csinálunk, az négy enum-tag.
