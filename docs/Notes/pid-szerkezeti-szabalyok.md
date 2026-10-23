---
topic: A P&ID-k szerkezeti szabályai — mit írnak elő a mérnököknek, és mit tud ebből egy szintetikus generátor
status: draft
date: 2026-09-12
related: [10-literature/pid-structural-rules.md, 40-design/splitter.md, ADR-0007, pid-lapkozi-csatlakozok.md, open100-rendszerkodok.md]
---

# A P&ID-k szerkezeti szabályai: mitől lesz egy generált rajz „szabályalapú"?

## Miért van ez

A dolgozat nem valódi gyári rajzokon méri a visszakeresést, hanem **generált** üzemeken. A pyDEXPI-vel felépítünk egy nagy üzemgráfot, a splitter lapokra vágja, és a lapközi csatlakozókból lesz a megoldókulcs. A brief szerint a professzor 2026-09-12-én megerősítette, hogy ez módszertanként elfogadható.

Egy bíráló ettől még joggal kérdezheti: *„honnan tudjátok, hogy a generált rajzok olyanok, mint a valódiak?"* Két válaszunk lesz:

1. **Statisztikai** (ADR-0007): a valódi lapok mérhető tulajdonságai beleesnek abba a tartományba, amit a generátor bejár.
2. **Szabályalapú** (ez a jegyzet): a generátor minden döntése mögött egy **leírt, idézhető mérnöki szabály** áll. Így a „szintetikus" azt jelenti, hogy *szabályokból épített*, és nem azt, hogy *kitalált*.

A forrásonként címkézett, részletes lista a `docs/private/10-literature/pid-structural-rules.md` fájlban van. Ez a jegyzet annak a tanító változata, **új tényt nem tartalmaz**.

## Jelölések

- **[ellenőrzött]**: 2026-09-12-én elolvastuk a forrás szövegét, és az mondja ki.
- **[nem ellenőrzött]**: tudjuk, vagy csak egy keresési találat állítja; a forrást nem olvastuk.
- **[nem olvasott]**: a forrás létezik, de nem volt elérhető.
- **[megfigyelés]**: valódi rajzon láttuk (OPEN100 vagy a Covestro-példa), de nincs rá leírt szabály.
- **[korábbi jegyzet]**: egy korábbi munkamenetben ellenőriztük, a megnevezett jegyzetben áll.

---

## Az alapgondolat

### Háromféle szabály

Toghraei P&ID-kézikönyvének előszava háromféle szabályt különít el, egy szelep példáján [ellenőrzött]:

1. **Fejlesztési szabály** (*development rule*): kell-e ide szelep, és ha igen, milyen típusú, milyen hajtással. Ez mérnöki döntés.
2. **Ábrázolási szabály** (*demonstration rule*): ha eldőlt, hogy kézi tolózár lesz, milyen jellel rajzoljuk.
3. **Rajzolási szabály** (*drafting rule*): vonalvastagság, betűméret, lapméret. Ezekkel a könyv kifejezetten nem foglalkozik.

**Nekünk az 1. kell a generátorhoz** (mi mihez kapcsolódik), és **a 3. lapokra vonatkozó része a splitterhez**. A 2. a képi megjelenítésé, ami most nincs soron (splitter.md 4. kérdés: előbb tiszta gráf, a kép később).

### Miért követik a rajzok ezeket a szabályokat?

- **Sok szakág ugyanazt a rajzot olvassa.** Toghraei a P&ID-t a vegyi üzem „bibliájának" nevezi. Használja a technológus, a műszeres, a csővezeték-tervező, a gépész, a légtechnikus és az építész, és a P&ID-ből készül többek között a csőizometria, a berendezés- és műszerlista, a vezetéklista és a hurokrajz [ellenőrzött].
- **Biztonság és üzemeltetés.** A HAZOP-megbeszélés (szisztematikus veszélyelemzés) főleg a P&ID-n folyik. Üzem közben a karbantartók a P&ID alapján zárják le és jelölik meg a berendezést javítás előtt (*lockout–tagout*) [ellenőrzött, Toghraei 1.1].
- **Gyors átláthatóság és konfigurációkezelés.** A Hanford-eljárás szerint a szabványos P&ID lehetővé teszi, hogy bárki gyorsan átlássa a rendszert. A P&ID a projekt legfontosabb információforrása és a konfigurációkezelés dokumentációja. Két kimondott célja a rendezett információközlés és az, hogy a későbbi módosítások ne okozzanak sok átrajzolást [ellenőrzött, HNF 3.2, 3.2.1].
- **A rajz él.** Kiadási mérföldkövei: IFR (véleményezésre), IFA (jóváhagyásra), IFD (tervezésre), IFC (kivitelezésre), végül a megvalósulási állapot (*as-built*) [ellenőrzött, Toghraei 2.2]. Ezért kér a Hanford helyet a jövőbeli módosításoknak, és ezért nem törölnek lapot apróság miatt.

**A lényeg:** a szabályok azért vannak, hogy **egy idegen mérnök is ugyanott keresse ugyanazt**. Nekünk ebből következik, hogy ha a generált rajz ugyanezeket a szabályokat követi, a visszakereső rendszernek ugyanazokra a jelekre kell támaszkodnia, mint egy valódi rajzon.

---

## Honnan jönnek a szabályok, és mennyire hihetünk nekik?

Egy dolgozatban nem mindegy, honnan idézünk. A forrásoknak erősségi sorrendjük van:

| Forrás | Mi ez | Mennyire erős | Mit olvastunk belőle |
|---|---|---|---|
| **ISO 10628-1:2014** | nemzetközi szabvány a vegyipari folyamatábrákról és P&ID-kről | a legerősebb, de általános | a hivatalos előnézet 1–5.4. fejezetét |
| **HNF-64103** (Hanford, 2020) | egy amerikai energiaügyi (DOE) vállalkozó nyilvánosan kiadott eljárása; saját szavaival „a kivételektől eltekintve" egyezik a PIP (Process Industry Practices) szabvánnyal | erős és nagyon konkrét, de egy telephely gyakorlata | a teljes szöveget |
| **KLM Technology Group** projektszabvány (2011) | olaj-, gáz- és petrolkémiai tervezési szabvány egy oktatócégtől; a bevezető részt ingyen közzéteszik | közepes | az ingyenes első 23 oldalt (146-ból) |
| **Toghraei:** *Piping and Instrumentation Diagram Development* (Wiley, 2019) | gyakorlati kézikönyv; saját szavaival „ökölszabályok könyve" | közepes–erős | a kiadói előnézetet (előszó, 1–2. fejezet, 3. fejezet eleje). A szabályok a 4. fejezettől kezdődnek, azokat nem olvastuk [nem olvasott]. |
| **pyDEXPI**, **DEXPI-példafájlok** | kód és adat | pontos arról, ami benne van | közvetlenül megvizsgáltuk |
| **Wikipedia** (KKS, IEC 81346, P&ID), **AIChE-blog** | másodlagos | gyengébb; csak ott használjuk, ahol más forrás is alátámasztja | a vonatkozó szakaszokat |

**Miért nem használtuk a PIP PIC001-et?** Ez az amerikai iparági „P&ID dokumentációs kritériumok" gyakorlat, és valószínűleg ez lenne a legjobb egyetlen forrás. A neten található teljes példányai (Scribd, pdfcoffee és társaik) **jogosulatlan feltöltések**. Egy dolgozat ezekre nem hivatkozhat, ezért nem építettünk rájuk. A hivatalos előnézet nem töltött le (HTTP 403). A helyettesítő a Hanford-eljárás, mert kimondja, hogy a PIP-pel egyezik. Toghraei könyvével, az iráni IPS-E-PR-230 szabvánnyal és Towler–Sinnott tankönyvével ugyanez a helyzet.

**Tanulság kutatáskezdőnek:** az „ezt mindenki így csinálja" nem forrás. Az a forrás, amit el tudsz olvasni, és meg tudsz nevezni, hogy melyik bekezdés mondja.

---

## A négy szint egy táblázatban

| Szint | Kérdés | Példa | Kinek szól a generátorban |
|---|---|---|---|
| **1. Helyi minta** | Mi van egy berendezés körül? | a szivattyú szelepei | pyDEXPI-minta |
| **2. Kapcsolódás** | Mi mihez köthető? | a közmű csonkkal kapcsolódik | csatlakozó-szabály, generátorfüggvény |
| **3. Lap** | Hogyan lesz belőle rajzsorozat? | a lapközi csatlakozó felirata | splitter |
| **4. Üzem** | Hogyan kódoljuk az egészet? | KKS: `1 2LAC03 CT002 QT12` | címkegenerátor, splitter |

---

## 1. szint: helyi minták (egy berendezés és a szerelvényei)

### Kidolgozott példa 1: a centrifugálszivattyú

Két egymástól független forrás, a Hanford-eljárás és a KLM-szabvány lényegében ugyanazt írja elő [ellenőrzött]:

```
   SZÍVÓOLDAL                                                   NYOMÓOLDAL

 ──►──[elzáró]──[szűrő]──►──( SZIVATTYÚ )──►──┬──[visszacsapó]──[elzáró]──►──
                                  │           │
                            [légtelenítő]    (PI)
                             szeleppel    nyomásmérő
```

Balról jobbra, forrással:

1. **Szívóoldali elzáró szelep.** KLM: „Pump suction valve". A Hanford is feltételezi: az ideiglenes szűrő „a szivattyú és a szívóoldali elzáró közötti első karimás kötésnél" van [ellenőrzött].
2. **Szűrő.** Centrifugálszivattyúnál a Hanford ideiglenes szívószűrőt engedélyez: indítás előtt beszerelik, az első üzemi szakasz után kiveszik. Forgó (rotary) szivattyúnál állandó, kivehető kosaras szűrő kell [ellenőrzött].
3. **Visszacsapó szelep a nyomóoldalon, a szivattyú és az elzáró között.** Hanford szó szerint: *„check valve will be located between block and pump"*. A KLM szerint a „wafer" (tárcsás, karimák közé szorított) visszacsapót lehetőleg kerülni kell [ellenőrzött]. Hogy a visszacsapó a visszaáramlást akadályozza meg, általános mérnöki tudás; ebben a kutatásban forrásból nem olvastuk [nem ellenőrzött].
4. **Nyomásmérő a nyomócsonk és a visszacsapó között.** Mindkét forrás így írja [ellenőrzött].
5. **Légtelenítő a szivattyúházon, szeleppel** (Hanford); a leürítőket és légtelenítőket a céljukkal együtt kell rajzolni (KLM) [ellenőrzött].
6. **Térfogatkiszorítású (pl. dugattyús) szivattyúnál külső biztonsági lefúvatás kell** (Hanford) [ellenőrzött]. A DEXPI saját referencia-rajzán pontosan így van: a dugattyús szivattyú nyomóoldali elágazásából egy rugóterhelésű biztonsági szelep vezet vissza a tartályba [ellenőrzött, a fájlból kiolvasva].

**Amit a források nem mondanak meg:**
- *Mikor* kell **minimális átfolyású visszavezetés** (min-flow line). A KLM felsorolja a rajzolandó részletek között, de feltételt nem ad [ellenőrzött, hogy nincs ott].
- A KLM egy DN20-as (¾ hüvelykes) **melegítő megkerülőt** is említ a visszacsapótól a nyomóvezetékig, „a 8.1.4. pontban megadott esetekben". Az a pont nem az ingyenes részben van [nem olvasott].

**Tartalék szivattyúk.** Az ISO 10628-1 szerint a P&ID-n szerepelnie kell a **beépített tartalék berendezésnek**. A KLM szerint a tartalékot „Spare" felirat jelöli [ellenőrzött]. A folyamatábrán (PFD-n) viszont a Hanford szerint általában csak egy példányt rajzolnak az azonos sorokból és tartalékokból [ellenőrzött, a PFD-szakaszban]. Innen jönnek az OPEN100 `RCS-PU-102A` / `102B` típusú A/B párjai.

### Kidolgozott példa 2: a szabályozószelep-állomás

Hanford: *„In general, control valve stations have block valves and a by-pass."* Vagyis: általában a szabályozószelep állomásnak két elzárója és egy megkerülő ága van. A rajzon fel kell tüntetni a szabályozószelep méretét és azt, hogy hiba esetén hova áll, valamint a megkerülő szelep méretét. A KLM ugyanezt kéri: az állomás elzáró- és megkerülőszelepeinek méretét, és a szelep levegőkimaradáskori helyzetét, **FC** (zár), **FO** (nyit) vagy **FL** (helyben marad) [ellenőrzött].

```
               ┌───────────────[megkerülő szelep]───────────────┐
 ──►───────────┤                                                ├───────────►──
               └──[elzáró]──[ SZABÁLYOZÓSZELEP  FC/FO/FL ]──[elzáró]──┘
```

**Figyelj az „in general" szóra.** Nem minden szabályozószelepnek van állomása. A generátorban ezért ez **valószínűség**, nem kötelező szabály.

Rokon, forrással igazolt ok a megkerülőre: a KLM szerint hőcserélőnél megkerülő kell, ha a karbantartást üzemelő egység mellett végzik [ellenőrzött]. Hogy a szabályozószelep-állomás megkerülője ugyanezt a célt szolgálja, ésszerű, de erre nem olvastunk forrást [nem ellenőrzött].

### Kidolgozott példa 3: biztonsági szelep (PSV) egy tartályon

Hanford [ellenőrzött]:

```
        TARTÁLY
           │
       [elzáró]      ← nyitott állapotban lezárva vagy plombálva, teljes átömlésű
           │
           ├──[leürítő szelep vagy vakdugó]   ← az elzáró és a PSV között
           │
         [PSV] ──► lefúvató rendszer
        méret, szűkítő jele, szelepszám, nyitónyomás
```

A KLM szerint a biztonsági szelep általában a tartály **felső kilépő vezetékén** ül, vagy közvetlenül a tartályon [ellenőrzött].

**Hőtágulási lefúvató (thermal relief).** A Hanford szerint olyan folyadékkal teli vezetékre kell, amelyet mindkét végén el lehet zárni, ha a nyomás a tervezési nyomás **1,5-szeresére** nőhet. Továbbá **minden vízhűtésű hűtőnek** kell hőtágulási lefúvató a visszatérő hűtővíz-vezetéken, a hűtő és az elzáró között [ellenőrzött]. A hűtőre vonatkozó rész beépíthető a mintába. Az 1,5-szörös feltételt viszont a generátor nem tudja ellenőrizni, mert a gráfunkban nincs tervezési nyomás.

### Tartályok leürítése és légtelenítése: itt a források ellentmondanak

- **KLM:** minden tartályon és oszlopon szelepes leürítő (a helyére szabály is van), felül vakkarimás légtelenítő, a tetején egy helyi nyomásmérő, a felső kilépő vezetéken egy helyi hőmérő [ellenőrzött].
- **Hanford:** magaspont-légtelenítőt és leürítőt csak akkor rajzolnak, ha zárt rendszerbe köt, vagy technológiai vagy biztonsági ok miatt kell [ellenőrzött].

A generátorban ez tehát **konvenció-paraméter** („minden leürítő látszik" vagy „csak a zárt rendszerbe kötők"). **Tanulság:** amit „a" P&ID-szabálynak hiszel, az sokszor „egy" cég szabálya.

### Műszerek, címkék és hurkok

- **A címke felépítése.** Funkcióbetűk (az ISA-5.1 szabvány alapján) és egy hurokszám; a hurokszámozás cégenként más; a betűk és a szám **együtt** egyediek [ellenőrzött, AIChE-blog]. A Hanford és a KLM is egyedi azonosítót kér minden műszerre [ellenőrzött].
- **Egy címke lebontva** (AIChE-blog) [ellenőrzött]: `PDIT1703` = **P** nyomás, **D** különbség (módosító), **I** kijelző, **T** távadó; 1703 a hurokszám. Tehát nyomáskülönbséget kijelző távadó.
- **A betűk sorrendje** (Wikipedia, másodlagos) [ellenőrzött]: legfeljebb 5 betű, sorban: mért mennyiség, módosító, kijelző (passzív) funkció, kimenő (aktív) funkció, funkciómódosító. Például `FIC045` a 045-ös hurok áramlásjelző szabályozója, és ugyanebben a hurokban lehet egy `FT045` áramlás-távadó.
- **A hurok felépítése.** Az „érzékelő → távadó → szabályozó → beavatkozó szelep" lánc kötelező szabályként **egyik olvasott forrásban sem szerepel így** [nem ellenőrzött szabályként]. A DEXPI referencia-rajza viszont szerkezetében így építi fel a hurkot: jelképző funkció → jeltovábbító funkció → beavatkozó funkció → beavatkozó rendszer (a szelep). A rajzon 4 hurokfunkció és 3 beavatkozó rendszer van [ellenőrzött, a fájlból megszámolva]. Hogy melyik beavatkozó melyik hurokhoz tartozik, azt nem vizsgáltuk. Ez jó sablon egy műszeres mintához.
- **A bonyolult reteszelési logika nem a P&ID-n van.** KLM: „fekete doboz", hivatkozással egy külön lapon lévő logikai rajzra. Hanford: logikai táblázat, külön P&ID vagy logikai rajz [ellenőrzött].

### Vezetékszám és specifikációváltás

A Hanford szerint minden technológiai és közmű-vezetéknek van vezetékszáma, és **ahol a csőspecifikáció megváltozik, ott új vezetékszám kezdődik** [ellenőrzött]. Hogy a vezetékszám milyen mezőkből áll (átmérő, közeg, sorszám, csőosztály…), azt a `pid-lapkozi-csatlakozok.md` jegyzet magyarázza [korábbi jegyzet].

---

## 2. szint: mi mihez kapcsolódhat

1. **Az irány a rajz része.** ISO 10628-1: az áramlási útvonalat és irányt vonalak és nyilak jelzik; a fő áramlási irány balról jobbra és fentről lefelé halad [ellenőrzött].
2. **A pyDEXPI jelenleg csak ennyit ellenőriz: bemenő csatlakozó csak kimenőhöz köthető** [ellenőrzött, kódból]. Nem tudja, hogy gőzvezeték ne kössön hűtővízhez, és nyomásfokozatot sem ismer. Minden további kapcsolódási szabályhoz saját csatlakozóosztályt kell írni.
3. **A közmű (utility) csonkkal kapcsolódik, nem átmenő vezetékkel.**
   - **Hanford:** a közművezeték a berendezés mellett kezdődik és végződik. Csak annyi hosszt rajzolnak, amennyi a szelepekhez, a műszerekhez és a vezetékszámhoz kell, a végét pedig csak felirat jelzi. **A fő közműgerincek nem az egység P&ID-jén vannak, hanem a terület közmű-P&ID-jén** [ellenőrzött].
   - **KLM:** a közművezeték egy dobozban végződik, benne a szolgáltatás rövidítése (a szabvány példái: CWS, CWR, IA). A lap címmezője mellett egy „közmű-azonosító táblázat" mondja meg, melyik rajzon van a szolgáltatás [ellenőrzött]. A rövidítések feloldását (hűtővíz előremenő, hűtővíz visszatérő, műszerlevegő) a KLM A. függeléke tartalmazza, amit nem olvastunk [nem ellenőrzött].
   - **ISO 10628-1:** a közmű-folyamatábrán a technológiai berendezés feliratos dobozként szerepel, a közmű-csatlakozásaival [ellenőrzött].
4. **A más egységbe menő vezetéket másképp jelölik.** KLM: a lap **alján**, dobozban: a vezeték szolgáltatása, a forrás- vagy célegység neve és száma, a kapcsolódó rajz száma koordinátával. Hanford: az egységen kívülre menő vezetéknél általános név és berendezésszám [ellenőrzött].
5. **A segédrendszerek külön rajzon vannak.** ISO: téglalap keret, hivatkozással a külön rajzra. Hanford: a kompresszor kenőolaj- és tömítőolaj-rendszere külön segéd-P&ID-n [ellenőrzött].
6. **A jelvezeték nem cső.** A KLM szerint a lapok között átmenő műszer-, vezérlő- és szoftverjeleket külön dobozban zárják le: benne a folytatódó műszer száma, a helye és a rajzszám [ellenőrzött]. A pyDEXPI DEXPI-mintái csak csővezeték-csatlakozót fogadnak el [ellenőrzött, kódból].
7. **Tiltott kapcsolatokról nincs lista.** Egyik olvasott forrás sem sorolja fel, mit tilos összekötni [ellenőrzött hiány]. A szabálygráfos javító cikk (arXiv 2502.18493) 33 szabályából csak 5-öt mutat be [korábbi jegyzet].
8. **Az azonosítóknak minden dokumentumban egyezniük kell.** A Hanford szerint az azonosítók egyezzenek a berendezéslistával, az adatlapokkal és a P&ID-kkel [ellenőrzött]. Az OPEN100 `RC-P102A` / `RCS-PU-102A` eltérése tehát **szabálysértés**, ami a valóságban mégis előfordul [korábbi jegyzet]. A benchmark „rendetlen címke" módja ezt modellezi, nem egy konvenciót.

---

## 3. szint: hogyan lesz egy üzemből rajzsorozat

### Amit a források kimondanak

- **Folytonosság a lapok között.** ISO 10628-1: ha egy rajz több lapból áll, *ajánlott*, hogy a be- és kimenő vezetékek ugyanazon a magasságon folytatódjanak, amikor a lapokat egymás mellé tesszük. A másik rajzon folytatódó vezeték végeit **kölcsönösen** hivatkozni kell [ellenőrzött].
- **Balról jobbra, lapról lapra.** Hanford: a betáplálás balról lép be, a termék jobbra lép ki, és a technológiai áramnak lapról lapra folytonosnak kell lennie. Rajzolás előtt meg kell keresni a vezetékek folytatását a szomszédos rajzokon [ellenőrzött].
- **A nagyobb számú rajz jobbra van.** KLM: az egységen belüli más rajzokról jövő vagy oda menő vezetékek a lap bal vagy jobb szélén végződnek. A nagyobb számú rajz felé jobbra, a kisebb felé balra [ellenőrzött]. **Ebből következik, hogy a rajzszámok a folyási iránnyal nőnek.**
- **Közmű-P&ID és segéd-P&ID külön lap** (2. szint, 3. és 5. pont). Toghraei szerint a közműelosztó P&ID-ket vázlatosan, de felülnézetben rajzolják [ellenőrzött].
- **Jelmagyarázat-lap.** Hanford: minden jelnek visszakereshetőnek kell lennie egy jelmagyarázatban, ami vagy a lapon van, vagy egy hivatkozott külön rajzon. Az AIChE-blog ezeket „lead sheet"-nek (jelmagyarázat-lapnak) hívja. Toghraei szerint a lap hivatkozott rajzok blokkjában a jelmagyarázat-lapok a legfontosabbak [ellenőrzött].
- **Tételjegyzék.** A KLM szerint minden rajz jobb felső részén egy „Item Index" sorolja fel a fő berendezéseket a koordinátáikkal. Emellett **külön lapon** össze kell foglalni az egység vagy üzem összes berendezését, a hivatkozott P&ID-vel és a hellyel [ellenőrzött]. **Ez az egyetlen leírt szabály, ami megmondja, hol keresd egy berendezés lapját.**
- **Rács.**
  - KLM: 50 mm-es osztás, hosszában 1–23, szélességben A–P [ellenőrzött].
  - OPEN100: A–H és 1–12, H van fent, az 1-es oszlop jobbra [korábbi jegyzet].
  - Covestro-példa: A–L és 1–16 [megfigyelés].
- **Lapméret.** Nincs egységes méret [ellenőrzött]:
  - ISO: A1-et javasol.
  - KLM: A0, egyszerű rajzhoz A1.
  - Toghraei: cégenként más, például D (amerikai) vagy A1.
  - DEXPI referencia-rajz: A3.
- **Lapnév és lapszám.**
  - Toghraei: a lapnév a tartalom szerint készül, és **soha ne legyen benne berendezésszám**, mert az megváltozhat. Lapot apró ok miatt, például tartalomáthelyezés miatt, nem törölnek.
  - DEXPI: minden rajz metaadatában van rajzszám, lapszám és összes lapszám. A referencia-rajzon ezek értéke „123/A93", „2a" és 4 [ellenőrzött].

### Amit egyetlen olvasott forrás sem mond meg

- **Hány berendezés fér egy lapra.** A Hanford csak annyit mond, hogy a rajz ne legyen zsúfolt, egyenletes sűrűségű legyen, és maradjon hely a módosításoknak [ellenőrzött]. **Számot senki nem ad.** A `splitter.md` „kb. 5–15 fő berendezés laponként" mondatának ezért **nincs forrása**.
- **Mi szerint osztják lapokra a sorozatot** (egység, rendszer vagy darabszám szerint). Csak közvetett jeleink vannak:
  - A DEXPI metaadatai minden rajzot területhez, szakaszhoz, rendszerhez, sorhoz és egységhez kötnek [ellenőrzött].
  - A Covestro-rajz címe „Reaktion Str.1 Teil 2", vagyis az 1. reakciósor 2. része [megfigyelés].
  - Az OPEN100 rendszerenként bont [korábbi jegyzet].
  - A Hanford logikai alrendszerekbe csoportosít, például „reakció" és „termékkinyerés", de ezt a **folyamatábrára** mondja [ellenőrzött, PFD-szakasz].

### A lapközi csatlakozó felirata: három leírt és két valódi változat

| Honnan | Mi áll a feliraton | Címke |
|---|---|---|
| **Hanford** | szállított közeg → forrás vagy cél (egységen belül a berendezésszám, kívül általános név és berendezésszám) → rajzszám, lap és zóna | [ellenőrzött] |
| **KLM** | a vezeték szolgáltatása → kiinduló vagy cél berendezés száma → a folytatódó rajz száma koordinátával | [ellenőrzött] |
| **DEXPI adatmodell** | hivatkozott rajzszám és hivatkozott csatlakozószám. A DEXPI saját referencia-rajzán ez a hivatkozás **üres** | [ellenőrzött] |
| **OPEN100** (atomerőmű) | bejövő: `PID 120-1 (C-1)` és a küldő rendszer kódja; kimenő: a célrendszer neve és `RCS-PID-100-2` | [korábbi jegyzet] |
| **Covestro-példa** (vegyipar, 2020) | német szolgáltatásszöveg, a partneregység előtagjával kezdődő kód, egy háromjegyű szám és a partnerrajz száma, pl. `Kühlwasser-Rücklauf` (hűtővíz visszatérő), `LA01-WA112 276`, `UER-2345678` | [megfigyelés, PDF-szövegből] |

Fontos részlet a Covestro-példából: az egyik rajz **15** felirata nevezi meg a másikat, a másik rajz viszont csak **2** felirattal hivatkozik vissza [megfigyelés]. A „minden zászlónak megvan a párja" tehát még egy hivatalos DEXPI-példában sem igaz. (A párok helyzetét a rajzon nem néztük meg, csak a kinyert szöveget.)

### Kidolgozott példa 4: egy egység rajzsorozata, szabályról szabályra

Ez **képzeletbeli példa**. A lapbeosztás maga kitalált, mert nincs rá szabály. Minden lépésnél megmondjuk viszont, melyik leírt szabály szól bele.

**Az egység:** betáplálótartály → két szivattyú (A és B) → hőcserélő → reaktor → termékhűtő → terméktartály. Közmű: hűtővíz. A reaktoron egy nyomásszabályozó hurok van.

```
 [Jelmagyarázat-lap]     [Tételjegyzék: az egység összes berendezése]     [Közmű-P&ID: hűtővíz-gerinc]
          ▲                               ▲                                     ▲
          │ hivatkozás (minden lapról)    │ hivatkozás                          │ szolgáltatás-doboz (CWS/CWR)
          │                               │                                     │ (sok lapról, nem párosával)
   ┌──────┴──────┐   cső-pár    ┌─────────┴───┐   cső-pár    ┌──────────────────┴──┐
   │   101-es    │ ───────────► │   102-es    │ ───────────► │       103-as        │
   │ tartály     │  jobb szél → │ hőcserélő   │  jobb szél → │ termékhűtő          │
   │ PU-A, PU-B  │  ← bal szél  │ reaktor+PIC │  ← bal szél  │ terméktartály       │
   └─────────────┘              └─────────────┘              └─────────────────────┘
```

1. **A lapok sorrendje a folyást követi.** 101-es lap: tartály és szivattyúk; 102-es: hőcserélő és reaktor; 103-as: hűtő és terméktartály. Szabályok: Hanford (lapról lapra folytonos), KLM (a nagyobb szám jobbra). *Hogy egy lapra hány berendezés kerül, az döntés, nem szabály.*
2. **Mindkét szivattyú a 101-es lapon van, teljes szerelvénnyel.** Szabályok: ISO (a tartalék rajta van), Hanford és KLM (szerelvény, 1. kidolgozott példa).
3. **A 101 → 102 átmenet.** A 101-es lap jobb szélén egy kimenő, a 102-es bal szélén egy bejövő csatlakozó van (KLM). A felirat a Hanford szerint: közeg, a cél berendezés száma (a hőcserélőé), rajz 102, lapszám, zóna. A 102-es lapon ugyanez áll visszafelé, mert a hivatkozás kölcsönös (ISO).
4. **Hűtővíz a termékhűtőn (103).** Nem húzunk vezetéket a közmű-lapig. A hűtő mellett egy rövid csonk van, dobozban `CWS` / `CWR`, a lapon pedig közmű-azonosító táblázat (KLM). A hűtővíz-gerinc a terület **közmű-P&ID-jén** van (Hanford). A hűtőn hőtágulási lefúvató van a visszatérő ágon (Hanford).
5. **A reaktor nyomásszabályozója a 102-es lapon van**, a szelep állomással, ahogy az általában szokás (Hanford). Ha a hurok jele átmenne egy másik lapra, külön jelcsatlakozó doboz kellene, benne műszerszám, hely és rajzszám (KLM).
6. **Hivatkozások.** Minden lap hivatkozza a jelmagyarázat-lapot (Hanford, Toghraei), és az egységnek van külön tételjegyzék-lapja (KLM).
7. **Metaadat.** Minden lapon van rajzszám, lapszám, összes lapszám, és az üzemi hierarchia kódjai (DEXPI).

**Figyeld meg a két különböző kapcsolatfajtát.** A **cső-pár** egy-egy kapcsolat: egy csatlakozó az egyik lapon, a párja a másikon. A **szolgáltatás-doboz** egy-a-sokhoz hivatkozás: sok lap mutat ugyanarra a közmű-P&ID-re, és ott nincs „párja" a doboznak. A mostani splitter csak az elsőt ismeri (lásd lent).

---

## 4. szint: az üzem kódolása

### KKS (erőművi azonosító rendszer): egy példa lebontva

Forrás: német Wikipédia, tehát másodlagos; az eredeti VGB-szabványt nem olvastuk [ellenőrzött, másodlagos]. A KKS-azonosító 15–17 karakteres, és háromféle kódolása van: technológiai, beépítési hely szerinti és térbeli. A technológiai kódnak négy szintje van:

| Szint | Formátum | Rész a példában | Jelentés |
|---|---|---|---|
| 0: teljes létesítmény | `A` vagy `N` | `1` | az 1-es blokk |
| 1: funkció | `(N)AAANN` | `2LAC03` | **2L**: 2. gőz-víz körfolyamat · **A**: tápvízrendszer · **C**: tápszivattyú-rendszer · **03**: a harmadik |
| 2: aggregát | `AANNN(A)` | `CT002` | **C**: közvetlen mérés · **T**: hőmérséklet · **002**: a második |
| 3: eszköz | `AANN` | `QT12` | **Q**: irányítástechnikai eszköz · **T**: védőcső vagy merülőhüvely · **12**: a tizenkettedik |

(`A` = betű, `N` = szám, zárójelben az opcionális karakterek.)

Összeolvasva: `1 2LAC03 CT002 QT12` = az 1-es blokk harmadik tápszivattyú-rendszerének második hőmérsékletmérésén a tizenkettedik merülőhüvely.

Két szabály, ami a generátornak fontos:
- **A számozás iránya általában az anyagáram folyási iránya.**
- **A technológiai kódolás P&ID alapján készül.**

A KKS utódja az RDS-PP (2007), ami az IEC 81346-ra épül.

**Az OPEN100 nem KKS-t használ**, hanem saját rendszerkódokat (RCS, CND, FWS…) és `PID 100` típusú rajzszámokat [korábbi jegyzet: `open100-rendszerkodok.md`]. A projekt egyetlen valódi, többlapos rajzsorozata tehát sem a KKS, sem az IEC 81346 formátumát nem követi.

### IEC/ISO 81346

- Három „nézőpont" (aspektus) jele: **`=`** funkció, **`-`** termék, **`+`** hely [korábbi jegyzet: `ontology-landscape.md`].
- A 81346-14 (RDS-MS) a gyártó- és feldolgozórendszerekről szól, és még végleges tervezet [ellenőrzött, másodlagos].
- Az ISO 10628-1 szerint a rajzon a jelölés *történhet* az IEC 81346 szerint. Ez lehetőség, nem kötelezettség [ellenőrzött].

### A DEXPI metaadat-hierarchiája

A DEXPI referencia-rajz metaadataiban ez a lánc szerepel, mindegyik szinthez kóddal és névvel [ellenőrzött, a fájlból kiolvasva]:

```
vállalat → telephely → ipari komplexum → üzem → terület → szakasz → rendszer → sor (train) → folyamatcella → egység
```

A példában a szakasz neve „Utilities" (közművek). Ha a generátor minden rajzhoz kiírja ezeket a kódokat, a splitter **egység vagy rendszer szerint** tud vágni, és ez az a vágás, amit a források alátámasztanak.

### A Covestro-példa kódjai

A két rajz címmezőjében `COVPIL1-V999-TA99` és `COVPIL1-V999-LA01` áll. A más egységbe menő vezetékszám a **partneregység** előtagjával kezdődik, például `LA01-LR045…`. A műszercímkék `PI P0020`, `LIC L0012` alakúak [megfigyelés]. Ez egy második, vegyipari kódolási kultúra az OPEN100 mellett.

---

## Mit jelent ez a generátornak

### A pyDEXPI négy „bekötési pontja"

Szabály csak ezen a négy helyen kerülhet be a pyDEXPI generálásába [ellenőrzött, kódból]:

1. **Minta (pattern).** Egy kész kis P&ID-darab, például egy szivattyú a szerelvényeivel, bemenő és kimenő csatlakozóval. **Ide kerülnek az 1. szint szabályai.**
2. **Csatlakozó-kompatibilitás** (`assess_valid_counterpart`). Eldönti, hogy két csatlakozó összeköthető-e; ma csak annyit tud, hogy bemenő ↔ kimenő. **Ide kerülhet:** közmű csak közműhöz, jel csak jelhez, azonos csőosztály.
3. **Generátorfüggvény** (`GeneratorFunction`). Eldönti, mi jön következőnek; a mellékelt változat „teljesen véletlen". **Ide kerül:** a betáplálás → … → termék sorrend, az egységek, az A/B tartalékok.
4. **Lezáró függvény** (`CappingFunction`). A generálás végén nyitva maradt csatlakozókat zárja le. **Ide kerülhet:** a közműcsonk szolgáltatás-dobozzal, vagy a más egységbe menő vezeték.

Ezeken kívül két hely van még, de már a pyDEXPI-n kívül:
- **Utólagos ellenőrzés:** szabálygráfok illesztése a kész rajzra, az arXiv 2502.18493 módszerével.
- **Splitter:** lapokra vágás és a csatlakozók feliratozása.

### Mi van most a pyDEXPI mintáiban, és mi nincs

- A pip-csomag nem tartalmaz mintát. A GitHub-tárolóban **10 eloszlás és 23 minta** van [ellenőrzött].
- **Egyikben sincs műszer, visszacsapó szelep vagy szelepállomás.** Szelepből csak az általános `OperatedValve` szerepel, a `pump_pattern_3` pedig egy csupasz szivattyú [ellenőrzött]. **A fenti szabályok közül egy sincs benne.**
- A minták eredete sehol nincs leírva, a pyDEXPI-cikk sem ír róla [ellenőrzött].
- Licenc: AGPL-3.0 [ellenőrzött].
- A minták pickle-fájlok. Hogy a pickle betöltéskor kódot futtathat, általános Python-tudás, ma nem olvastuk [nem ellenőrzött]. A vizsgálathoz ezért olyan módszert használtunk, ami nem futtat kódot.

### Lánc vagy gyűrű: miért nem ad elágazó üzemet a mintakészlet

Ez **levezetés a kódból és a mintafájlokból; még nem futtattuk**.

Minden köztes mintának pontosan egy bemenete és egy kimenete van. A „feed"-nek csak kimenete, a „product"-nak csak bemenete. Minden lépés egy nyitott csatlakozót elhasznál, és legfeljebb egy újat hoz. A nyitott csatlakozók száma tehát soha nem nő, és ebből csak ez a két alak jöhet ki:

```
 feed ─► pump ─► hxer ─► reactor ─► product            (lánc)

 pump ─► hxer ─► reactor ─┐
   ▲──────────────────────┘                             (gyűrű: egyetlen visszavezetés)
```

Nincs elágazás, nincs közmű, nincs több egység. Egy láncon a splitter három valószerű stratégiája szinte ugyanazt a vágást adja. Hirtreiter és munkatársai generátora ezért használ **több kimenetű** mintákat: így jönnek létre az elágazások [ellenőrzött].

### Honnan lehetne jó mintát venni?

- **DEXPI TrainingTestCases** (CC BY 4.0). Az I01–I15 műszeres példák hurok-sablonnak jók [ellenőrzött, hogy léteznek; a tartalmukat nem vizsgáltuk]. A C01 referencia-rajz centrifugálszivattyúján viszont **nincs egyetlen szelep sem**, ezért a szivattyúszabály példájának nem jó [ellenőrzött].
- **A szerelvény-mintákat nekünk kell megírni** a fenti, forrással igazolt szabályokból. Kész, géppel olvasható, licencben tiszta szerelvénykönyvtárat nem találtunk.

---

## Mit jelent ez a splitternek

**Amit a szabályok alátámasztanak:**
- A **lapsorrend a folyást követi**, ahogy a `flow_greedy` csinálja (Hanford, KLM, ISO, KKS számozási iránya).
- A **szerelvény a berendezéssel együtt utazik**, ahogy a `_cluster_owners` csinálja (1. szint).
- **Minden vágásnak kölcsönös hivatkozása van**, ahogy a `ConnectorPair` biztosítja (ISO).

**Ahol ütközés vagy hiány van:**
1. **A `utility_aware` a rossz dolgot mozgatja.** A nagy fokszámú *berendezéseket* teszi külön lapra. A szabályok szerint viszont a közmű**gerinc** kerül a közmű-P&ID-re, **a fogyasztó berendezés az egység lapján marad**, egy szolgáltatás-dobozos csonkkal. Ráadásul a közműkapcsolat egy-a-sokhoz hivatkozás, nem pár.
2. **A csatlakozó felirata szegény.** Hiányzik belőle a közeg vagy szolgáltatás, a forrás- vagy célberendezés (illetve egység), és a zóna. Ezeket mindhárom leírt forrás kéri.
3. **Nincs különbség az egységen belüli és a más egységbe menő vágás, illetve a cső és a jel között.** A KLM és a Hanford ezeket másképp jelöli.
4. **A lapkeretnek nincs forrása.** Az „5–15" szám egyik olvasott forrásban sem szerepel.
5. **A `modularity` nem egyenlő az „egység szerint" vágással.** Az egység tervezői címke, nem gráfközösség. A szabályhű vágás a generátor által kiírt egységkód szerint történne.
6. **A berendezés-duplikálásnak (`IdentityGroup`) nincs leírt szabálya.** Az OPEN100-ban látjuk [korábbi jegyzet], de leírt szabályként csak a feliraton szereplő berendezésszám és a tételjegyzék-lap létezik.

---

## Tipikus félreértések

- **„Van szabvány arra, hány berendezés fér egy lapra."** Az olvasott források egyikében sincs szám. Csak annyi áll bennük, hogy a lap ne legyen zsúfolt.
- **„A PIP PIC001 szabadon olvasható a neten."** A neten lévő teljes példányok jogosulatlanok; egy dolgozat nem hivatkozhat rájuk.
- **„A P&ID-szabályok egyetemesek."** Többnyire cégszabályok, és ellentmondanak egymásnak: leürítők (KLM vs. Hanford), lapméret (A0, A1, A3, D), felirat (öt változat). Ezek a generátorban paraméterek, nem konstansok.
- **„A pyDEXPI mintái szabálykövető szivattyúkat adnak."** Nem. Egyik mintában sincs visszacsapó szelep, műszer vagy szelepállomás.
- **„Szintetikus = kitalált."** Csak akkor, ha nem tudjuk megmondani, melyik szabályból jön. Ha minden elemhez forrás tartozik, a rajz szabályalapú.
- **„A közműfogyasztó a közmű-lapra kerül."** Nem, a gerinc kerül oda. A fogyasztó a saját lapján marad, csonkkal.
- **„Minden lapközi hivatkozás kölcsönös."** Az ISO szerint annak *kell* lennie, de a Covestro-példában 15 hivatkozásból 2-nek van visszafelé párja.
- **„Az OPEN100 KKS-kódokat használ, mert atomerőmű."** Nem, saját rendszerkódokat használ.
- **„A SynthPID szabályalapú generátor, ezt használhatnánk."** Nem szabályalapú: 12 valódi OPEN100-rajz szerkezetét variálja. Ráadásul pont az OPEN100-ra épül, amit mi validációra tartogatunk (ADR-0007), és a kódtárát ma nem találtuk.
- **„Ha a szabály forrásból van, az oka is."** Nem. A források gyakran csak a szabályt írják le. Az okot (például hogy mire jó a visszacsapó) külön kell igazolni, különben [nem ellenőrzött] marad.

---

## Ha egy dolgot olvasol el

[HNF-64103, *Preparation of Process Flow Diagrams and Piping and Instrumentation Diagrams* (Hanford, 2020)](https://hmis.hanford.gov/files.cfm/HNF-64103_-_Rev_00.pdf). A **3.2.2** (elrendezés), **3.2.4** (szabályozószelep, biztonsági szelep, hőtágulási lefúvató) és **3.2.5** (csővezeték, közmű, szivattyú) pont összesen kb. öt oldal. Ez a legkonkrétabb nyilvános, jogtisztán olvasható P&ID-szabálygyűjtemény, amit találtunk, és kimondja, hogy egyezik a PIP gyakorlatával.
