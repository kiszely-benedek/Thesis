---
topic: Mi van egy valódi P&ID-n, és miért — ISA-5.1 jelölés, helyi és hurokba kötött műszerek, szabványos szerelvények, technológiai egységek, csővezeték-számok
status: draft
date: 2026-10-25
related: [40-design/generator-v2-realism.md, ADR-0057, 10-literature/real-pid-composition-2026-10.md, 10-literature/pid-structural-rules.md, pid-szerkezeti-szabalyok.md, open100-rendszerkodok.md, pid-lapkozi-csatlakozok.md]
---

# Hogyan épül fel egy valódi P&ID — és mit tanul ebből a v2 generátor

## Miért van ez a jegyzet

A mostani (v1) generátor egyszerű üzemeket rajzol: 6 berendezésfajta, 3 szelepfajta, véletlen fa alakú
csőhálózat, és minden műszer egy szabályozókörben ül. Te (2026-10-24) azt kérted, hogy a generált rajzok
**szinte teljesen olyanok legyenek, mint a valódiak**. Ehhez először érteni kell, *mi van* egy valódi rajzon, és
*miért pont az*. A P&ID-n ugyanis szinte semmi sem díszítés: minden szelepnek, műszernek, vezetékszámnak üzemeltetési
vagy biztonsági oka van. Ez a jegyzet ezeket az okokat magyarázza el, példákkal.

A számok forrása a `docs/private/10-literature/real-pid-composition-2026-10.md` (jelölése ott: [C] = mi számoltuk,
[V] = elolvastuk a forrást, [P] = korábbi projektjegyzet). **Fontos megkötés:** az egyetlen nyilvános, valódi,
többlapos P&ID-sorozat, amit ismerünk, az OPEN100 12 lapja — ez **egyetlen atomerőmű** rajzai. Ami „valódi" szám
alább, az ennek az egy üzemnek a rajzolási szokását írja le.

## 1. Mi van egy valódi lapon — számokkal

Egy valódi lap közepén általában **egy-két nagy berendezés** áll (egy kolonna, egy tartály, egy kemence), körülötte a
hozzá tartozó szivattyúk, hőcserélők, és **rengeteg szelep és műszer**. A Ford, Bacon & Davis tervezőiroda gyakorlati
ajánlása [V]: egy lapra **egy kolonna**, **egy kemence**, **egy bonyolult kompresszor**, **1–2 tartály**, és a
szivattyúkat a szívóoldali tartályukkal együtt rajzolják.

| Laponként (átlag) | OPEN100 (valódi) | Mai generátor (v1, fejléc-korpusz) |
|---|---|---|
| Berendezés | 1–9 rajzonként [P, hiányos lista] | 14,7 |
| Szelep | 21,4 (9–35) | 15,0 |
| Műszer (buborék) | 29,2 (9–49) | 5,2 |
| Lapközi csatlakozó | 8,0 (2–12) | 5,2 |
| Összes „szimbólum" | 82,3 (40–134) | 42,6 csomópont |

Tanulság: a valódi lap **berendezésben ritkább**, **szelepben és műszerben sűrűbb**, mint a miénk. A műszerek
69 %-a (350-ből 242) egyetlen vonallal kapcsolódik a rajzhoz [C]: a műszer **a csőre „lóg rá"**, nem a cső
része.

## 2. Az ISA-5.1 jelölés: mit jelent a FIC-101?

A műszereket az amerikai ISA-5.1 szabvány betűkódjával jelölik (a szabvány szövegét nem olvastuk, csak egy másodlagos
forrás táblázatát [V]). A jel két részből áll: **betűk** és **hurokszám**.

- **Első betű — mit mérünk** (mért változó).
- **Esetleges módosító** — pl. D = különbség, Q = összegzés, F = arány, S = biztonsági.
- **Következő betűk — mit csinál a műszer** (kijelez, szabályoz, távadóként továbbít, kapcsol …).
- **Funkciómódosító** — pl. H = magas, L = alacsony, HH = nagyon magas (vészhatár).
- **Hurokszám** — ugyanaz a szám az egy körbe tartozó összes elemen.

| Első betű | Jelentés | Utóbetű | Jelentés |
|---|---|---|---|
| F | áramlás (flow) | T | távadó (transmitter) — jelet küld |
| L | szint (level) | I | kijelző (indicator) |
| P | nyomás (pressure) | C | szabályozó (controller) |
| T | hőmérséklet (temperature) | V | szelep (valve) |
| A | analízis (pl. összetétel) | S | kapcsoló (switch) |
| S | fordulatszám (speed) | A | riasztás (alarm) |
| V | rezgés (vibration) | E | érzékelő elem (element) |
| Z | helyzet (position) | G | üveg, nézőke (gauge glass) |
| H | kézi (hand) | Y | segédfunkció, pl. mágnesszelep |
| X | „szabadon választott", szokás szerint **nyitó-záró (on-off) szelep** | Q | (módosítóként) összegzés |

**Példák:**

| Jel | Kiolvasva | Mit csinál |
|---|---|---|
| **FIC-101** | Flow Indicating Controller, 101-es hurok | áramlásszabályozó, kijelzi és szabályozza az áramlást |
| **FT-101** | Flow Transmitter, 101-es hurok | méri az áramlást és továbbítja a jelet a FIC-101-nek |
| **FV-101** | Flow Valve, 101-es hurok | a FIC-101 által mozgatott **szabályzószelep** |
| **PT-203** | Pressure Transmitter, 203-as hurok | nyomástávadó (pl. egy Rosemount 3051 ilyen eszköz) |
| **PI-204** | Pressure Indicator | **helyi nyomásmérő óra** — csak kijelez, a helyszínen leolvasható |
| **LG-210** | Level Gauge (glass) | szintjelző üveg a tartály oldalán |
| **LSHH-305** | Level Switch High-High | vészkapcsoló: ha a szint túl magas, leold |
| **XV-305** | on-off szelep, 305-ös hurok | a LSHH-305 lezárja — gyakran **mágnesszelep** (solenoid) működteti, ennek jele XY-305 |
| **ZSO-305 / ZSC-305** | Position Switch Open / Closed | végálláskapcsoló: jelzi, hogy az XV nyitva vagy zárva van |
| **PDT-401** | Pressure Differential Transmitter | nyomáskülönbség, pl. egy szűrő két oldala között (eltömődés figyelése) |
| **FQI-501** | Flow totalizing Indicator | összegzi az átfolyt mennyiséget (pl. tartályparki elszámolás) |
| **FFIC-601** | Flow ratio Controller | két áram arányát tartja (keverésnél) |

A **hurok** (loop) az együtt dolgozó elemek csoportja: érzékelő → távadó → szabályozó → szelep. A közös szám
köti össze őket a rajzon: FT-101, FIC-101, FV-101.

**A v2 generátor jelei** ugyanezt a nyelvtant követik, csak a hurokszám elején az egység száma áll, a végén
háromjegyű sorszám: a 12-es egység 14. hurka `FIC-12014`, `FT-12014`, `FV-12014`. A berendezéseké
`típuskód-egység+kétjegyű sorszám+tartalékbetű`, pl. `P-1203A` (12-es egység 3. szivattyúja, „A" példány).

## 3. Helyi műszer és hurokba kötött műszer

| | Helyi (local, field) műszer | Hurokba kötött műszer |
|---|---|---|
| Példa | PI nyomásmérő óra, TI hőmérő, LG szintüveg, FI rotaméter | PT → PIC → PV; LT → LSHH → XV |
| Hol olvassák | a helyszínen, a berendezés mellett | a vezérlőteremben (DCS) |
| Kapcsolat a rajzon | egy vonal a csőhöz vagy a tartályhoz — **„levél"** a gráfban | jelvezetékek (szaggatott vonal) más műszerekhez és egy szelephez |
| Miért kell | indításnál, karbantartásnál, ellenőrzésre | automatikus szabályozás, riasztás, védelem |

A valódi lapokon a helyi műszerek vannak többségben — ezért lóg a műszerek 69 %-a egyetlen vonalon. A mai generátor
csak hurokba kötött műszert rajzol; a v2 mindkettőt.

**Hogyan ül egy műszer a csövön?** A DEXPI saját mintarajzán (C01) a nyomástávadó így kapcsolódik: a csövön egy
**T-idom** (leágazás), a leágazásban egy **gyökérszelep** (root valve — ezzel lehet a műszert a csőtől elzárni
karbantartáshoz), és a műszer ennek a végén „ül". A v2 pontosan ezt a szerkezetet használja.

## 4. Szabványos szerelvények — miért van ott az a szelep?

A „trim" vagy „typical" egy berendezés körüli, mindig ugyanúgy felépülő szelep- és műszercsoport. A szabályok
forrása főleg a HNF-64103 (amerikai energiaügyi minisztériumi alvállalkozói eljárás, 2020) és a KLM
tervezési szabvány; részletesen: `pid-szerkezeti-szabalyok.md`, L1–L16 szabályok.

### 4.1 Szivattyú

```
tartály ──[elzáró]──[szűrő]──► SZIVATTYÚ ──(PI)──[visszacsapó]──[elzáró]──► tovább
```

- **Szívóoldali elzáró szelep** (L2): a szivattyút ki lehet venni karbantartásra úgy, hogy a tartály nem ürül le.
- **Szűrő a szívóoldalon** (L2): védi a járókereket a szennyeződéstől, főleg az első indításkor (ideiglenes
  kúpos szűrő); forgódugattyús szivattyúknál állandó kosaras szűrő.
- **Visszacsapó szelep a nyomóoldalon** (L1): ha a szivattyú leáll, a nyomóvezetékben nagyobb a nyomás, és a folyadék
  visszafolyna a szivattyún át — visszafelé pörgetné, és leürítené a fogadó tartályt. Két párhuzamos szivattyúnál
  (A/B) a futó szivattyú az álló tartalékon keresztül nyomna vissza. A visszacsapó szelep ezt megakadályozza.
- **Miért a visszacsapó van közelebb a szivattyúhoz, és utána az elzáró?** (L1, HNF szó szerint ezt írja elő.)
  Így az elzáró szeleppel a visszacsapót is le lehet választani, ha javítani kell.
- **Nyomásmérő a szivattyú és a visszacsapó között** (L3): a kezelő itt látja, hogy a szivattyú valóban nyom-e.
- **Térfogat-kiszorításos (PD) szivattyú biztonsági szeleppel** (L5): egy dugattyús szivattyú zárt szelep ellen is
  tovább nyom, amíg valami el nem törik; ezért a nyomóoldalról egy biztonsági szelep vezet vissza a szívóoldalra.
- **Minimális áramlás megkerülő** (L6): egy centrifugálszivattyú nulla átfolyásnál túlmelegszik. Egy szűkítőn
  (restriction orifice) át kis áramot visszavezetnek a tartályba. A forrás felsorolja, de **nem mondja meg, mikor
  kötelező** — a generátorban ez egy valószínűség.

### 4.2 Szabályzószelep-állomás

```
           ┌──────────[megkerülő szelep, kézi]──────────┐
──[T]──[elzáró]──[szűkítő]──[SZABÁLYZÓSZELEP]──[szűkítő]──[elzáró]──[T]──
```

- **Miért kell megkerülő (bypass)?** (L9) Hogy a szabályzószelepet javítani lehessen **úgy, hogy az üzem megy
  tovább**: a két elzáró szelepet bezárják, és a kezelő kézzel, a megkerülő szeleppel szabályoz.
- **Miért elzárók?** Hogy a szabályzószelepet ki lehessen szerelni.
- **Szűkítő idomok:** a szabályzószelep gyakran kisebb, mint a cső.
- A HNF szövege: „általában" van megkerülő — tehát nem mindig. A generátorban ez is valószínűség.
- Egy már meglévő érdekesség: a dolgozat LLM-primerje (`primer_pid_v1.txt`) már most is azt mondja a modellnek, hogy
  a szabályzószelep-állomásoknak általában van elzárója és megkerülője — a v1 rajzai ezt nem mutatták, a v2-éi igen.

### 4.3 Tartály, kolonna, edény

- **Biztonsági szelep (PSV) minden nyomástartó edényen** (L10, L11): túlnyomás ellen véd (tűz, elzárt kimenet,
  szabályozási hiba). A PSV a tartály tetején vagy a felső kivezetésen ül. Ha elzáró szelepek is vannak előtte-utána,
  azokat **nyitott állásban leplombálják** (car-sealed open), hogy véletlenül se zárják el a védelmet.
- **Leürítő és légtelenítő** (L13): alul egy ürítőszelep, felül egy légtelenítő vakkarimával — karbantartáshoz.
  **A források itt ellentmondanak:** a KLM szerint minden edényre kell, a HNF szerint csak ha zárt rendszerbe
  vezet vagy biztonsági ok kéri. A generátorban ez egy kapcsoló.
- **Szintmérés:** szintüveg (LG) helyben, szinttávadó (LT) a szabályozáshoz, és gyakran egy külön vészkapcsoló
  (LSHH), ami egy XV-t zár — ez a túltöltés elleni védelem.
- **Légköri tartály szellőzője:** lélegeztető szelep (breather valve) és lángzár (flame arrestor).

### 4.4 Hőcserélő

- Hűtővizes hűtőn **hőtágulás elleni biztonsági szelep** a visszatérő ágon (L12): ha mindkét oldalon elzárják, a
  bent rekedt víz felmelegszik és kitágul.
- Gőzfűtésnél **kondenzedény (steam trap)** a kondenzátum kivezetésén (L15).
- A **segédközeg-vezetékek** (hűtővíz, gőz) a rajzon csak egy rövid csonkig látszanak, a szolgáltatás kódjával
  (CWS = hűtővíz előremenő, CWR = visszatérő); a fő gerincvezeték egy külön „utility" rajzon van (C4 szabály).

## 5. Tartalék gépek: A/B(/C)

Ami leállhat és fontos, abból **beépített tartalék** van: két egyforma szivattyú, `P-1203A` és `P-1203B`, egyik
megy, a másik áll. A rajzon mindkettő szerepel (ISO 10628: a beépített tartalékot rajzolni kell). Az OPEN100-ban a
felsorolt 43 berendezésből 15 ilyen betűs csoport tagja (≈ 35 %) [P].

**Miért fontos ez a dolgozatnak?** A lapokon átnyúló azonosság (ugyanaz a tárgy két lapon) a dolgozat második
hozzájárulása. Az A/B pár ennek a valósághű nehéz esete: a két jel csak egy betűben különbözik.

## 6. Technológiai egységek és laponkénti rajzolásuk

| Egység | Fő elemek | Jellemző hurkok | Hány lapra kerül |
|---|---|---|---|
| **Desztilláló kolonna** | kolonna, visszaforraló (reboiler), kondenzátor, reflux-tartály, reflux- és fenékszivattyúk A/B | kolonnanyomás, reflux áramlás, reflux-tartály szint, fenékszint, tányérhőmérséklet → gőzszelep | jellemzően 2: (1) kolonna + visszaforraló + fenékszivattyúk, (2) kondenzátor + reflux-tartály + refluxszivattyúk; néha 1 („Column Systems Combined", FB&D) |
| **Kompresszorfokozat** | szívóoldali cseppleválasztó (KO drum), kompresszor, utóhűtő | túlpumpálás elleni (anti-surge) visszavezetés, szívónyomás, KO szint + vészleállítás | 1 (FB&D: egy bonyolult kompresszor laponként); a kenőolaj-rendszer külön segédrajz |
| **Kemence–reaktor–szeparátor** | betáp/elfolyó hőcserélő, kemence + ventilátor, reaktor, hűtő, szeparátor | kemence kimeneti hőmérséklet → tüzelőgáz, lángőr (BSL) → XV, szeparátornyomás, szeparátorszint | 3 (egy kemence laponként) |
| **Tartálypark** | 2–4 tartály, átfejtő szivattyúk, mérőszakasz | túltöltés elleni XV, átfejtési áramlás, összegző (FQI) | 1–2 tartály laponként |
| **Hőcserélősor** | 2–4 hőcserélő sorban | kimeneti hőmérséklet → megkerülő szelep | 1 |

Hogyan függnek össze a lapok: egy vezeték, ami lefut a lapról, egy **lapközi csatlakozóban** (off-page connector)
végződik, ami megnevezi a folytatás rajzát; a másik lapon a párja ugyanígy visszautal (`pid-lapkozi-csatlakozok.md`).

## 7. Csővezeték-szám

Minden vezetéknek saját száma van (C3 szabály), és a szám maga is információ. Az OPEN100 formája
`SIZE-RCS-100007-SPEC-HC-X`: méret, rendszerkód, hatjegyű szám, csőosztály, szigetelés. A Ford, Bacon & Davis lista
[V]: csőméret, szolgáltatás (közeg) kódja, sorszám, csőosztály (specifikáció), szigetelés típusa és vastagsága,
kísérőfűtés.

A v2 formája: `6-P-120017-A1A-N`

| Mező | Példa | Jelentés |
|---|---|---|
| méret | `6` | 6 hüvelykes cső (idézőjel nélkül, hogy a kérdésekben egy szónak számítson) |
| közeg | `P` | folyékony technológiai közeg (PG = gáz, CWS = hűtővíz, LPS = kisnyomású gőz, FL = fáklya) |
| szám | `120017` | 12-es egység, 17. vezeték |
| csőosztály | `A1A` | a cső anyaga és nyomásfokozata (kitalált, de valósághű kódok) |
| szigetelés | `N` | nincs (H = meleg, C = hideg, HT = kísérőfűtés) |

**Szabály (L20):** ahol a csőosztály megváltozik (pl. egy nyomáscsökkentő szelep után), ott új vezetékszám kezdődik.

## 8. Mit vesz át ebből a v2 generátor — és mit nem

**Átveszi:** 25 berendezésfajtát, 31 csőidom- és szelepfajtát, kb. 20 ISA műszertípust, a 4. fejezet
szerelvényeit, az A/B tartalékokat, a 6. fejezet egységeit („mintáit"), a vezetékszámokat, és azt, hogy egy lap
egy nagy berendezés köré épül, 3–10 berendezéssel.

**A mostani v1 nem változik:** minden eddigi mérés (EXP-0001, EXP-0002, a demó üzemei) bájtra pontosan
reprodukálható marad. A v2 külön, új nevű korpuszokat ad (`D100g2`, `H100g2` …).

**Amit nem tudunk, és nem is állítunk:**
- **Nincs publikált gyakoriság** arra, hogy egy valódi P&ID-n hány gömbcsap vagy hány nyomástávadó van fajtánként
  (egyetlen cikk sem közöl ilyet). Ezért a fajták aránya a generátorban **tervezési paraméter**, és utólag
  ellenőrizzük, hogy a laponkénti összesítések beleesnek-e az OPEN100 tartományába.
- A szabályozási sémák (melyik változót melyik szelep szabályozza) bevett tankönyvi gyakorlatot követnek, de ezt a
  projektben egyetlen elolvasott forrás sem írja le szabályként — ezért **döntésként** vannak jelölve.
- A segédközeg-gerincvezetékek (gőz, hűtővíz fővezeték) továbbra is parkolnak; csak a fogyasztói csonkok kerülnek a
  rajzra.

## Kis szótár

| Kifejezés | Jelentés |
|---|---|
| P&ID | csővezeték- és műszerezési folyamatábra (Piping and Instrumentation Diagram) |
| trim / typical | egy berendezés köré mindig ugyanúgy épülő szelep- és műszercsoport |
| elzáró szelep (block valve) | teljesen nyit vagy zár, nem szabályoz (pl. tolózár, gömbcsap) |
| szabályzószelep (control valve) | egy szabályozó jele szerint részben nyit; a jele xV (FV, LV, PV, TV) |
| on-off szelep (XV) | távvezérelt nyitó-záró szelep, gyakran mágnesszeleppel; vészleállításhoz |
| visszacsapó szelep (check valve) | csak egy irányba enged áramlást |
| biztonsági szelep (PSV) | túlnyomásnál magától nyit |
| gyökérszelep (root valve) | a műszer leágazásán, a műszert választja le a csőről |
| hurok (loop) | érzékelő → távadó → szabályozó → szelep, közös számmal |
| helyi műszer | a helyszínen leolvasható (óra, hőmérő, szintüveg) |
| beépített tartalék (A/B) | két azonos gép, az egyik a másik helyére tud állni |
| lapközi csatlakozó | a lapról lefutó vezeték vége, a folytatás rajzszámával |
