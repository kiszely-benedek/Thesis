# A nagy kép — merre tartunk, és jó-e az irány

*Első változat: 2026-09-27. Átírva: 2026-11-22, frissítve 2026-11-28 az EXP-0009 eredményeivel. Szabad szöveges
összefoglaló a commitok mögötti szerkezetről. A számok forrása a `30-experiments/_results.md`, az
`EXP-0008-v2-rerun.md` és az `EXP-0009-v22-sealed.md`, a döntéseké a `20-decisions/`.*

## A végcél

Egy valódi vegyi üzem P&ID-dokumentációja nem egy rajz, hanem több száz lap. Egy cső az egyik lap szélén „kilép”,
és egy másik lapon folytatódik; ugyanaz a szivattyú több lapon is megjelenik. Aki kérdezni akar erről az üzemről
— „ha ezt a tartályt el akarom zárni, mely szelepeket kell bezárnom?” —, annak az egész csomagot egyben kell
látnia. A meglévő kutatások (ChatP&ID, PIDQA) mind **egyetlen lapon** működnek.

A dolgozat végcélja ezért egy rendszer, amely **(1)** sok lapból egyetlen tudásgráfot épít — ez a cím első fele,
„tudásgráf-építés P&ID-rajzokból” —, és **(2)** erre a gráfra kérdés-válasz rendszert tesz, amely akkor is működik,
amikor az üzem már nem fér bele egy nyelvi modell „fejébe” — ez a cím második fele, „skálázható Q&A rendszer”.

A kiinduló állítás az volt, hogy a módszerek rangsora **megfordul** a méret növekedésével: ami egy lapon a legjobb
(az egész gráfot a promptba tenni), az üzemi méretben nem működik. A mérések ezt **részben igazolták, részben
cáfolták** (lásd lent): a gráflekérdező kaszkád minden mért méreten pontosabb volt, már egy lapon is. A méret azt
változtatja meg, mennyibe kerül és mennyi ideig tart a prompt-tömés, és hogy 67 lap fölött már be sem fér.

## Miért ebben a sorrendben építettünk

A sorrend a feladat logikáját követte: **amit nem lehet mérni, azt nem lehet állítani.** Először kellett egy
**benchmark**: generált üzemek, amelyeket úgy vágunk lapokra, hogy pontosan tudjuk, melyik cső melyik lapon
folytatódik — ez a „megoldókulcs” (ADR-0004, inverzió). Valódi, több száz lapos P&ID-csomag nyilvánosan nincs; a
professzor elfogadta, hogy a módszert generált üzemeken mutassuk be (ADR-0007). Utána jött a **tudásgráf-építés**
(a lapösszekötővel), majd a **kérdés-válasz rendszer**, és a végén a **fő kísérlet**, amely az egészet végigméri.

## Amit megcsináltunk

**A benchmark két generációja.** A v1 generátor véletlen fákból épít üzemet; ezen futott az első lezárt teszt. A
felülvizsgálat után készült a **v2**: folyamatminták (kolonna, kompresszor, tartálypark, hőcserélő-sor, szűrő stb.),
ISA-műszerezés, szokásos szelepcsoportok (trim), A/B tartalék-berendezések. A v2 az **OPEN100-hoz mért összetétel-
sávokon** belül van (pl. szimbólum/lap 85,7; sáv 56–109), de a sávokat mi tűztük ki egyetlen valódi üzemre, és a 40–134
szimbólumos lapok aránya csak 0,77 (cél 0,95, nem érvényesített). Ezután jött a **v2.2**: a generátor szabályait
kézikönyvekből vettük (Toghraei 2019, API RP 14C, Liptak), és minden üzemen 56 szabályt ellenőrzünk; a lezárt
üzemeken egyik sem sérült. A v2.2 tag nélküli szelepeket és szelepállásokat (nyitott, zárt, plombált) is rajzol.
Mérnöki szemmel ez sincs átnézve, de a szabályok forrása most már könyv, nem a saját ítéletünk.

**A tudásgráf-építés — kész.** A beolvasás (valódi DEXPI-fájl és generált üzem ugyanazon az úton), a megoldókulcs
elrejtése a lapösszekötő elől, a címke-alapú lapösszekötés és a Neo4j-betöltés. A lapokat nem tároljuk fájlként: a
memóriában `SheetGraph`-ok, a Neo4j-ben `Sheet` csomópontok, a korpusz a seedből újraépíthető.

**A kérdés-válasz rendszer — kész, befagyasztva.** A fő rendszer a **kaszkád** (V2T-A2): először egy olcsó Cypher-
lekérdezés próbálkozik, bizonytalanságnál egy gráfeszközöket használó ágens veszi át. A válaszok számított helyes
válaszok alapján pontozódnak, nem egy másik modell véleménye szerint (független LLM-audit: kappa 0,889).

**A fő mérés: EXP-0008 (lefutott 2026-11-17-én).** Tiszta újramérés, öt üzem skálánként, előre rögzített
állításokkal és $40-os plafonnal (a futás $26,56-ot használt a $30-ból).

| Mérés | Eredmény |
|---|---|
| Kaszkád pontossága ~100 lapon | 0,914 [0,895; 0,932] |
| Kaszkád pontossága ~1000 lapon | 0,908 [0,885; 0,932] |
| Különbség (Q4) | −0,005 [−0,035; +0,025], **PASS** |
| Költség kérdésenként | 0,00140 → 0,00155 $ |
| ContextRAG vs kaszkád, 1 / 3 / 11 lap | 0,779 / 0,566 / 0,592 vs 0,985 / 0,921 / 0,855 |
| ContextRAG költségaránya, 1 / 3 / 11 lap | 3,2× / 8,9× / 23,2× |
| ContextRAG kontextusfala | 67 lapnál |

**Ami elbukott, és ezt nyíltan kimondjuk:** az X1 és X2 előre rögzített állítás FAIL, mert a ContextRAG egy lapon
sem nyer. A késleltetési kritérium (K1) is FAIL, és az infrastruktúra-mérés (M1) is FAIL: az ágens-visszajátszások
a forrásfutás időit vették át.

**A második lezárt mérés: EXP-0009 (lefutott 2026-11-27-én).** Ugyanaz a befagyasztott kaszkád a nehezebb, v2.2-es
üzemeken, öt üzem skálánként, plusz egy feltáró B rendszer, amely a szelepállást és a tag nélküli szelepeket is
látja. Költség: $23,09 a $35-os plafonból.

| Mérés | Eredmény |
|---|---|
| Kaszkád (A2) ~100 / ~1000 lapon | 0,899 / 0,913; különbség +1,4 pont [−1,9; +4,7], **Q4 PASS** |
| A v2.2-es üzemek nehezebbek | −7,6 / −5,6 pont a v2.1-hez képest |
| K1 (kaszkád vs „mindig ágens”) | −3,1 pont, nem gyorsabb: **FAIL**, másodszor is |
| B: szelepállás | 0,96 (a „mindig a leggyakoribb” alapvonal 0,81) |
| Leválasztási kérdések | B 4–28 %, A2 3–16 % családonként: **nyitott probléma** |
| GLM 5.3 Flash a Luna helyett | 100 lapon −1,3, 1000 lapon −5,1 pont (egy-egy üzem) |
| Pontozó-audit | kappa 0,860; 25 eltérésből 0 pontozó- vagy gold-hiba |

A leválasztás utólagos elemzése szerint a gyenge eredményt csak kisebb részben okozza a definíció (legfeljebb kb.
15 pont a B-nél). A fő ok, hogy az ágens a szükséges szelepeknek csak kb. a felét sorolja fel (recall kb. 0,5,
precision kb. 0,78). Közben kiderült, hogy a befagyasztott útválasztó szabály a „cut … off” megfogalmazást nem
ismeri fel, ezért a lefelé irányuló kérdések először a Cypher-szintre mennek; ez a B-nél 11 jó ágensválaszt vitt el.

**A demo v2.** Angol nyelvű alkalmazás két üzemen (H100g21p1, H1000g21p1), a kérdés a kaszkádon át megy a
megfelelő szintre, külön eredmény-fülön mutatja az EXP-0008 számait. Az ingyenes visszajátszás-egyezés 10/10 mindkét
üzemen. Egy fizetős próbán (6 kérdés, $0,0103) egy kérdésnél a Cypher elfogadott, de rossz választ adott; ezt nem
javítottuk, mert a befagyasztott kaszkádhoz nem nyúlunk.

## Ami hátravan, és hová vezet

1. **A tanulási térkép átnézése** (te, folyamatban): a térkép állomásain végigmenni, és a nem érthető tételeket
   jelezni.
2. **A „megfordul” állítás átfogalmazása** (te döntöd el): a mérések szerint a pontossági optimum nem mozdul, a
   költség- és késleltetési oldal fordul. Ez az X1/X2 FAIL következménye; az EXP-0009 ezt megerősítette.
3. **A lapösszekötő tesztelése az OPEN100-on** (új terv): 12 valódi lap, 23 megbízhatóan összekötött pár. A
   címkék visszaállítása OCR-rel és kézi ellenőrzéssel történne.
4. **A mérnöki átnézés** (nyitott): egy kinyomtatott lap és a kérdéscsaládok megmutatása P&ID-t olvasó embernek.
5. **A P2 szakasz** (nincs jóváhagyva): az EXP-0009 kiegészítő része, saját jóváhagyás kell hozzá.

Kész, és ezért lekerült a listáról: precision, recall és F1 a mentett válaszokból (EXP-0009-ben számolva), a
gold-szúrópróba (48 kérdés és 500 leválasztási kérdés, 0 hiba).

## Jó-e az irány?

**Igen, és ezt az alábbiak igazolják:**
- A cím mindkét fele kész és mért: a tudásgráf-építés és a skálázható kérdés-válasz két lezárt mérésen is
  lefutott, és a skálaeredmény a nehezebb, kézikönyvi szabályú üzemeken is megismétlődött.
- A terep nyitott: a legutóbbi újdonság-ellenőrzés szerint senki nem publikált kérdés-válasz kiértékelést sok,
  egymással összekötött P&ID-lapon.
- Minden szám mérésből jön, a hibákat is megmutatjuk, és a siker feltételeit az első futás előtt rögzítettük.

**Amire figyelni kell — őszintén:**
- **A valósághűség a legnagyobb nyitott pont.** Generált üzemeken mérünk. A szabályok ma már kézikönyvből jönnek,
  de mérnöki átnézés nincs, és a kérdéscsaládokat mi találtuk ki. Ezt korlátként kell kimondani.
- **A leválasztás nincs megoldva.** Ez a mérnöki szempontból legfontosabb kérdéstípus, és itt a legrosszabb a
  rendszer. Ezt nyíltan kimondjuk; az okát (hiányos listák) már tudjuk.
- **A történet változott.** A „megfordul” állítás a saját méréseink szerint nem áll meg szó szerint; az
  átfogalmazás a dolgozat gerince.
- **Neked kell értened az egészet** — ezért jó, hogy a tanulási térképen végigmegyünk rajta.
