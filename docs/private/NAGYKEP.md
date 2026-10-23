# A nagy kép — merre tartunk, és jó-e az irány

*Írva: 2026-09-27. Szabad szöveges összefoglaló a commitok mögötti szerkezetről. A számok forrása a
`30-experiments/_results.md`, a döntéseké a `20-decisions/`.*

## A végcél

Egy valódi vegyi üzem P&ID-dokumentációja nem egy rajz, hanem több száz lap. Egy cső az egyik lap szélén „kilép”,
és egy másik lapon folytatódik; ugyanaz a szivattyú több lapon is megjelenik. Aki kérdezni akar erről az üzemről
— „ha ezt a tartályt el akarom zárni, mely szelepeket kell bezárnom?” —, annak az egész csomagot egyben kell
látnia. A meglévő kutatások (ChatP&ID, PIDQA) mind **egyetlen lapon** működnek.

A dolgozat végcélja ezért egy rendszer, amely **(1)** sok lapból egyetlen tudásgráfot épít — ez a cím első fele,
„tudásgráf-építés P&ID-rajzokból” —, és **(2)** erre a gráfra kérdés-válasz rendszert tesz, amely akkor is működik,
amikor az üzem már nem fér bele egy nyelvi modell „fejébe” — ez a cím második fele, „skálázható Q&A rendszer”. A fő
kísérlet azt mutatja meg, hogy a módszerek rangsora **megváltozik** a méret növekedésével: ami egy lapon a legjobb
(az egész gráfot a promptba tenni), az ezer lapon egyszerűen nem fér bele. Erre építünk egy saját,
**hierarchikus** módszert, amely előbb a megfelelő üzemrészt és lapot keresi meg, és csak ott keres tovább.

## Miért ebben a sorrendben építünk

A sorrend a feladat logikáját követi: **amit nem lehet mérni, azt nem lehet állítani.** Ezért először kellett egy
**benchmark**: generált üzemek, amelyeket úgy vágunk lapokra, hogy pontosan tudjuk, melyik cső melyik lapon
folytatódik — ez a „megoldókulcs”. Valódi, több száz lapos P&ID-csomag nyilvánosan nincs; a professzor elfogadta,
hogy a módszert generált üzemeken mutassuk be (ADR-0007). Utána jöhetett a **tudásgráf-építés**, mert a kérdés-válasz
rendszernek kell egy gráf, amin dolgozik. Csak ezután van értelme a **kérdés-válasz rendszernek**, és a legvégén a
**fő kísérletnek**, amely az egészet végigméri. Az írás ezzel párhuzamosan halad.

## Amit eddig megcsináltunk

**A benchmark megjavítása.** A lapokra vágás hibás volt. Amikor megmértük, milyen sűrűk a lapjaink egy valódi
DEXPI-laphoz képest, kiderült, hogy a lapoló a berendezéseket szinte véletlenszerűen szórja szét — nem jobb, mint a
vakszerencse (DENS-01). Megtaláltuk az okát (szélességi bejárás, `1731fae`), kijavítottuk, és újramértük: most egy
generált lap kb. 43 csomópontos (a valódi EX01: 36) és kb. 9 lapközi csatlakozója van (a valódi OPEN100-lapok: 8)
— SMOKE-06. Ez azért fontos, mert a fő kísérlet éppen azt méri, hány laphatáron kell átmenni egy válaszhoz; ha a
lapok irreálisak, a mérés is az.

**A tudásgráf-építés — kész.** Négy darabból áll, és mindegyiknek oka van:
- **Beolvasás** (`a5cf586`, `271cdf1`): egy valódi DEXPI-fájl (EX01) ugyanabba a formába kerül, mint a generált
  lapok, és egyetlen alkatrész sem vész el csendben. Így a valódi rajz és a generált üzemek ugyanazon az úton
  haladnak, és a ChatP&ID-vel való összevetés tisztességes.
- **A megoldókulcs elrejtése** (`5481943`): kiderült, hogy a lapok véletlenül elárulták, mi hová tartozik (közös
  belső azonosítók, a csatlakozó párja). Ha ezt nem zárjuk el, a lapösszekötő „puskázik”, és hamisan tökéletes. Ez a
  munka egyik legfontosabb tisztességi pontja.
- **Összekötés** (`3c97587`, `271cdf1`): a lapokat csak a rajzon látható feliratok alapján kötjük össze — ahogy egy
  mérnök tenné. Mérve 1 004 lapnál is hibátlan (SMOKE-04). Egy fontos eredmény már most van: ha a tagek a lapokon
  kicsit eltérő alakban szerepelnek, az összevonás teljesen elbukik (recall 0). Ez a valódi rajzokon előfordul, és
  itt lehet a munka egyik saját hozzájárulása.
- **Adatbázis** (`a94b6e6`, `1adc2dc`, `a634491`): az egész egy paranccsal betölthető a Neo4j-be; az 1 004 lapos üzem
  25 másodperc alatt (SMOKE-05). A határt (600 mp) a mérés *előtt* rögzítettük, hogy ne utólag igazítsunk hozzá.

**A kérdés-válasz rendszer — kb. félig.** Megvannak az alapkövek: a nyelvi modell hívása úgy, hogy minden válasz
elmentődik és pénz nélkül visszajátszható (`d48208b`, `64c56d5`), és fizetős hívás csak kifejezett engedéllyel
mehet ki; a közös válaszlépés, amelyen minden módszer ugyanúgy megy át, hogy csak a keresés különbözzön
(`083c7a6`); a válaszok pontozása számított helyes válaszok alapján, nem egy másik modell véleménye szerint
(`2b12dc5`); és a kérdésgenerátor első fele (`7b8845d`), amely minden kérdéshez kiszámolja a **k**-t — hány
laphatáron kell átmenni a válaszhoz. A k a fő kísérlet legfontosabb változója.

## Ami hátravan, és hová vezet

1. **A kérdés-válasz rendszer befejezése** (kb. egy hét): a kérdésgenerátor második fele és a k szerinti mintavétel;
   maguk a válaszadási módszerek — az „egész gráf a promptban” (ContextRAG), az adatbázis-lekérdezés (CypherRAG) és
   a **saját hierarchikus módszerünk**; a futtató és a jelentéskészítő.
2. **A pilot — az első fizetős mérés** (a te engedélyeddel): hol van a modell „kontextusfala”, mennyibe kerül egy
   kérdés, mennyire szórnak a válaszok. Ettől függ, hány kérdést engedhetünk meg magunknak. → *A kísérlet
   tervezésének alapja.*
3. **A ChatP&ID-összevetés** (EXP-0001): az ő 19 kérdésükből azokon, amelyekhez nem kell adatlap, reprodukáljuk-e az
   eredményüket egy lapon. → *Ez a horgony: megmutatja, hogy a mi megvalósításunk korrekt.*
4. **A fő kísérlet** (~10, ~100 és ~1 000 lap): a módszerek pontossága, költsége és ideje a méret és a k
   függvényében. A siker feltételeit előre rögzítettük (`qa-system.md` §13.3), hogy az eredményt ne utólag
   értelmezzük a javunkra.
5. **A lapösszekötő értékelése** a 23 valódi OPEN100-páron. → *Kis, de valódi ellenőrzés.*

## Jó-e az irány?

**Igen, és ezt az alábbiak igazolják:**
- A cím mindkét felét lefedi: a tudásgráf-építés kész és mért; a kérdés-válasz rendszer félúton van, és egyenesen
  a fő kísérlet felé tart.
- A terep valóban nyitott: a legutóbbi újdonság-ellenőrzés (2026-09-26) szerint senki nem publikált kérdés-válasz
  kiértékelést sok, egymással összekötött P&ID-lapon.
- A naptárhoz képest előrébb vagyunk: az október 4-i ellenőrzőpont tartalma már kész.
- Minden szám mérésből jön, minden döntés indokolva van — a védésen ez sokat ér.

**Amire figyelni kell — őszintén:**
- **Az írás a leglemaradóbb rész.** Javaslom, hogy a héten induljon el, a kód mellett. Ehhez kell a BME-sablon.
- **A pilot a legnagyobb ismeretlen.** Amíg nem mérjük meg a kontextusfalat és a költséget, nem tudjuk, mekkora
  kísérlet fér bele. Érdemes minél előbb lefuttatni — az engedélyeddel.
- **A hierarchikus módszer — a saját hozzájárulás — még nincs megtervezve.** Szándékosan: a görbék alapján
  tervezzük, de időben kell elkezdeni.
- **Generált adatokon dolgozunk.** Ez a módszertani dolgozatnál elfogadott (a professzor is elfogadta), de a
  dolgozatban nyíltan korlátként kell kimondani.
- **Neked kell értened az egészet** — ezért jó, hogy most együtt végigmegyünk rajta.

**A javasolt sorrend a következő napokra:** a kérdés-válasz rendszer befejezése → a pilot (engedéllyel) → a
ChatP&ID-összevetés → a fő kísérlet.
