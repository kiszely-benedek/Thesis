---
topic: P&ID lapközi csatlakozók — zászlók, irány, vezetékszám, rácsmező
status: draft
related: [ADR-0005, 40-design/open100-annotation.md, open100-rendszerkodok.md, open100-csatlakozo-megoldokulcs.md]
---

# P&ID lapközi csatlakozók: kilép a cső a lapról, vagy belép?

## Miért van ez

Egy P&ID (csővezeték- és műszerezési rajz) egy üzem egy darabjának csöveit, szelepeit, tartályait és műszereit mutatja. Egy egész erőmű nem fér egy lapra, ezért rendszerenként külön lapra rajzolják. A csövek viszont nem tisztelik a lap szélét: a reaktorhűtő lapon termelt gőz a frissgőz lapon köt ki. Valaminek meg kell mondania: "ez a cső amott folytatódik".

Ez a valami a **lapközi csatlakozó** (off-page connector): egy nyíl alakú, feliratozott doboz a lap szélén — a kódban és a jegyzetekben **zászló**. Ez az egyetlen dolog, ami tizenkét külön rajzból egy üzemet csinál. Nélküle minden lap sziget, és a "mi táplálja a gáztalanítót?" kérdésre nem lehet válaszolni arról a lapról, amelyiken a gáztalanító van.

## Az alapgondolat

Egy zászló egy lapközi kapcsolat **egyik vége**. A cső az A lapról egy **kimenő** zászlón át távozik, és a B lapra egy **bejövő** zászlón érkezik. Egy rendes rajzsorozatban mindkét vég megvan, és mindkettő megnevezi a másik lapot. Egy zászló elolvasása négy kérdés megválaszolása.

**1. Kilép vagy belép?** A csövön, a zászló mellett rajzolt **nyilat** nézd, ne a zászló helyét. Ha a nyíl a zászlóba mutat, az anyag elhagyja a lapot: kimenő. Ha a zászlótól elfelé, a rajz belseje felé mutat: bejövő. A rajzolók szokás szerint a bejövőket a bal, a kimenőket a jobb szélre teszik — ezt a konvenciót írja le a [piping-world P&ID-útmutatója](https://www.piping-world.com/what-is-a-piping-and-instrumentation-diagram-p-id) is —, de az OPEN100 több lapon megszegi. A nyíl az igazság, a lapszél csak tipp.

**2. Hová megy?** A zászló a másik rajzot **rajzszámmal és lapszámmal** nevezi meg: `PID 120-1` = a 120-as rajz 1. lapja. Az OPEN100-ban a két vég két különböző nyelvtant használ:

| Vég | Tipikus felirat | Mi micsoda |
|---|---|---|
| Bejövő | `PID 120-1 (C-1)` / alatta `RHRS` | rajz-lap, majd a **rácsmező**, ahol a másik zászló ül azon a lapon, majd a küldő rendszer **kódja** |
| Kimenő | `REACTOR COOLANT SYSTEM` / alatta `RCS-PID-100-2` | a célrendszer neve, majd kódja és a rajz-lap |

Csak a bejövő zászlókon van rácsmező. Ugyanazt a hivatkozást a rajzon többféleképp írják (`PID 120-1`, `PID-120-01`, `RCS-PID-100-2`), ezért a számokat kell összevetni, sosem a szöveget.

**3. Melyik cső ez? — a vonalak a zászlók között.** A zászlók között húzódó vonalak a **csövek**. Minden csőnek van egy **vezetékszáma**, a cső mellé írva. Az általános konvenció — az [AIChE "Codes, tags and labels"](https://chenected.aiche.org/2010/10/codes-tags-and-labels-interpreting-piping-and-instrumentation-diagrams) cikke magyarázza el a legtisztábban — mezők sorozata: névleges átmérő, közeg/rendszer kódja, sorszám, csőosztály (anyag, nyomásfokozat), szigetelés. Az OPEN100 előzetes terv, ezért az átmérő és a csőosztály még szó szerinti helykitöltő:

```
SIZE - RCS - 100007 - SPEC - HC - X
 │      │      │       │     │   └─ helykitöltő
 │      │      │       │     └───── szigetelés kódja
 │      │      │       └─────────── csőosztály, még nincs kiválasztva
 │      │      └─────────────────── a cső saját száma: EZ az azonossága
 │      └────────────────────────── annak a rendszernek a kódja, amelyé a cső ezen a lapon
 └───────────────────────────────── névleges átmérő, még nincs kiválasztva
```

A **szám az azonosság**. Az előtag ahhoz a laphoz tartozik, amelyiken állsz: ugyanaz a cső a kondenzátum lapon `SIZE-CND-165117`, a megcsapolt gőz lapon `SIZE-ESS-165117`, mert mindkét rajzoló a saját rendszere alá sorolja. Előtag-eltérés azonos számmal: normális. Szám-eltérés: másik cső.

A vastag vonal a főáramú cső, a vékony a kisebb ág vagy műszervezeték; a körök a műszerek (`TE` hőmérő, `PT` nyomásmérő, `FCV` szabályozószelep), a téglalapos, feliratozott alakzatok a berendezések. Amikor több vonal egy pontban összefut, az egy **összefolyás**: onnantól egy közös cső megy tovább, saját vezetékszámmal, ami már **egyik** eredeti csőé sem.

**4. Hol, a másik lapon?** A rácsmező. A lapok szélén rács van: A–H betűk oldalt (H fent), 1–12 számok fent (1 a jobb szélen). `(C-1)` = C sor, jobb szél. Arra való, hogy az olvasó a másik lapon keresés nélkül megtalálja a párt.

## Kidolgozott példa

5. lap (reaktorhűtő, 100-as rajz 1. lap), jobb szél, G sor. A zászló: `REACTOR COOLANT SYSTEM` / `RCS-PID-100-2`. A cső nyila a zászlóba mutat: kimenő, a 100-as rajz 2. lapjára. A cső mellett: `SIZE-RCS-100007-SPEC-HC-X`.

6. lap (100-as rajz 2. lap), bal szél, H sor. A zászló: `PID 100-1 (G-1)` / `RCS`. A nyíl a zászlótól elfelé mutat: bejövő, a 100-as rajz 1. lapjáról, ahol a pár a G sor jobb szélén ül. Egy mutatóvonal köti a `SIZE-RCS-100007-SPEC-HC-X` feliratot ehhez a csőhöz.

Azonos szám mindkét végen, mindkét vég a másik lapját nevezi meg, egy nyíl be, egy ki, a rácsmező a párra mutat: **teljesen igazolt pár**. A legtöbb pár nem ilyen tiszta; hogy akkor mi a teendő, a megoldókulcsról szóló jegyzet mondja el.

## Hová illik

Ez az oka, hogy a dolgozat valódi rajzokon mérhető. A PID2Graph annotációi szöveget nem tartalmaznak, a zászlók jelentése csak a képpontokban van; az ADR-0005 döntött úgy, hogy a 12 OPEN100 lapon ezt kézzel visszanyerjük, a terv az `open100-annotation.md`. A kapott párok a lapközi összekapcsolás megoldókulcsa (EXP-0004), a hiányzó rajzokra mutató zászlók pedig a "mondja meg a rendszer, hogy nem tudja" teszt (EXP-0005).

## Tipikus félreértések

- **"Bal szél = bejövő."** Nem. Az irányt a csövön lévő nyíl adja. Az OPEN100-ban van bal széli kimenő (4/16, 8/54) és jobb széli bejövő (6/28, 6/30).
- **"Más előtag = más cső."** Nem. `CND-165117` és `ESS-165117` egy cső. A szám dönt.
- **"A legközelebbi felirat ehhez a csőhöz tartozik."** Gyakran nem. Ahol több cső fut szorosan vagy összefolyik, a legközelebbi szöveg a szomszédé vagy a közös fejvezetéké lehet. A zászló saját nyilától kell végigkövetni a csövet a feliratáig.
- **"A rácsmező pontos."** Az OPEN100-ban hat hivatkozás egy sorral vagy oszloppal téved, egy pedig egy fejvezeték rossz végére mutat. Megerősítő tipp, nem kulcs.
- **"Minden zászlónak van párja."** Csak ha minden rajz a kezedben van. A készleten kívüli rajzra mutató zászló normális, és a rajzokban sima hibák is vannak.

## Ha egy dolgot olvasol el

[AIChE, "P&ID Part 4: Codes, Tags and Labels"](https://chenected.aiche.org/2010/10/codes-tags-and-labels-interpreting-piping-and-instrumentation-diagrams) — a legtisztább rövid leírás arról, hogyan épülnek fel a vezetékszámok és a feliratok.
