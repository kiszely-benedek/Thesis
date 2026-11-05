---
topic: Konfidenciaintervallum és bootstrap
status: draft
related: [ADR-0053, ADR-0063, EXP-0002, EXP-0004, src/plantgraph/exp0004/bootstrap.py, src/plantgraph/qa/cascade/evaluate.py]
---

# Konfidenciaintervallum és bootstrap

## Miért létezik

Az R5 zárt tesztjén a `cascade_v4_iso` a H100g2-n **401 / 440** kérdésre válaszolt jól (0,911), a
H1000g2-n **392 / 440**-re (0,891). Az első kérdés, amit egy bíráló feltesz: *ha holnap egy másik
440 kérdéses tesztsort húznánk ugyanabból a kérdéscsaládból, megint 0,911 jönne ki?* Nem pontosan.
Lehet 0,89, lehet 0,93 — a 440 kérdés **minta**, és a mintából számolt szám ingadozik.

Egyetlen szám (0,911) ezt az ingadozást elrejti. A konfidenciaintervallum (confidence interval, CI)
azt mondja meg: **mekkora ez az ingadozás**, vagyis mennyire bízhatunk a számban. Enélkül nem lehet
eldönteni, hogy a 0,911 és a 0,891 közti 2 százalékpont valódi különbség vagy csak szerencse.

## Az alapötlet

Egy 95 %-os konfidenciaintervallum egy **módszer**, ami egy mintából egy tartományt számol, és ez a
módszer — ha sokszor megismételnénk a mérést új mintákkal — az esetek kb. 95 %-ában lefedné a valódi
értéket. Az írásmód: `0,911 [0,881; 0,934]` — középen a mért érték, zárójelben az alsó és felső határ.

Hogyan számoljuk? Két út van:

1. **Képlet** — egyszerű arányra (helyes / összes) van zárt képlet, pl. a Wilson-intervallum.
2. **Bootstrap** — amikor nincs kényelmes képlet (F1, medián, két rendszer különbsége), a gép
   szimulálja az „új mintát”: az eredeti mintából **visszatevéssel** újrahúzunk ugyanannyi elemet,
   kiszámoljuk rá a mutatót, és ezt sokszor (nálunk 2000-szer) megismételjük. A 2000 eredmény
   középső 95 %-a (a 2,5. és a 97,5. percentilis közötti rész) az intervallum. Ezt
   **percentilis bootstrapnek** hívják.

Két finomítás, amit a projekt használ:

- **Páros (paired) bootstrap.** Ha két rendszert *ugyanazokon* a kérdéseken mérünk, nem a két
  intervallumot hasonlítjuk össze, hanem a **különbségre** számolunk intervallumot: minden
  újrahúzásnál ugyanazokat a kérdéseket kapja mindkét rendszer, és a különbségüket jegyezzük fel.
  Így a „mindkettőnek nehéz kérdés” hatása kiesik. (`qa/cascade/evaluate.py`, `paired_bootstrap`.)
- **Klaszteres (blokk-) bootstrap.** Az EXP-0004-ben a jelöltpárok nem függetlenek: az egy blokkba
  (azonos blokkolási kulcs) eső párok ugyanazokért az előfordulásokért versengenek. Ezért nem
  egyes párokat húzunk újra, hanem **egész blokkokat** (`exp0004/bootstrap.py`). Ha párokat húznánk,
  az intervallum hamisan szűk lenne, mert úgy tennénk, mintha több független adatunk volna.

## Kidolgozott példa

A 401 / 440 percentilis bootstrappal, futtatható Pythonban:

```python
import random

rng = random.Random(1)
data = [1] * 401 + [0] * 39          # 1 = helyes válasz, 0 = hibás
means = sorted(sum(rng.choices(data, k=440)) / 440 for _ in range(2000))
print(means[round(0.025 * 1999)], means[round(0.975 * 1999)])
# 0.884 0.936
```

Lefuttatva (2026-11-05) **[0,884; 0,936]** jön ki; a Wilson-képlet ugyanerre **[0,881; 0,934]**-et
ad — a két módszer itt szinte egyezik. A H1000g2 392 / 440-ére a Wilson-intervallum **[0,858; 0,917]**.

**A projekt saját számai, így olvasd őket:**

| Mért érték | Jelentés |
|---|---|
| D4 pár-F1 a H1000g2d100V-n: **0,950 [0,936; 0,962]** | A valódi F1 nagy biztonsággal 0,94 és 0,96 között van — szűk, mert sok blokk van. |
| D4 a névadási családon: **0,983 [0,973; 0,992]** | Még szűkebb és magasabb: a D4 itt szinte hibátlan. |
| I3: D4 − D2 a névadási családon: **+0,636 [+0,583; +0,691]** | Páros különbség. Az egész intervallum jóval 0 fölött van → a D4 előnye **nem lehet szerencse**. |
| R5 Q4: nagy − kis korpusz pontossága: **−0,020 [−0,059; +0,018]** | Az intervallum **tartalmazza a 0-t** → nem mutatható ki romlás 100-ról 1000 lapra. A Q4 állítás pont ezt kérte. |
| R5 K1: késleltetés-különbség: **+3,21 [+1,33; +5,25] s** | Végig 0 fölött → a kaszkád biztosan **lassabb**; ezért FAIL a K1. |

A szabály tehát: **nézd meg, hogy a különbség intervalluma tartalmazza-e a 0-t.** Ha igen, a mérés
nem tud dönteni; ha nem, az irány biztos.

## Hol illeszkedik

- **EXP-0002 / R5** (ADR-0053): minden állítás (Q4, K1, K2, K3, Q5) páros bootstrap-intervallumon
  dől el, a küszöböket előre rögzítettük.
- **EXP-0004** (ADR-0063): klaszteres bootstrap blokkokon, 2000 újrahúzás, rögzített `SEED = 20261104`,
  hogy az eredmény pontosan reprodukálható legyen.
- **A dolgozatban:** minden fő számot így írunk: *„0,911 (95 % CI: 0,881–0,934, n = 440)”*, a
  módszertani részben egyszer leírjuk, melyik fajta intervallumot használjuk és miért (páros,
  klaszteres, 2000 újrahúzás), és a következtetést mindig az intervallumra építjük, nem a pontértékre.

## Gyakori tévhitek

1. **„95 % az esélye, hogy a valódi érték az intervallumban van.”** Szigorúan véve nem: a valódi
   érték rögzített, a *módszer* talál 95 %-ban. A dolgozatban elég így írni: „95 %-os
   konfidenciaintervallum”, és nem kell valószínűséget mondani a konkrét tartományra.
2. **„Ha a két intervallum átfed, nincs különbség.”** Hamis. A 0,911 [0,881; 0,934] és a 0,891
   [0,858; 0,917] átfed, mégis a helyes kérdés a **páros különbség** intervalluma. Átfedő
   intervallumok mellett is lehet a különbség biztosan nem nulla, ha a mérések párosak.
3. **„A szűk intervallum azt jelenti, hogy jó a rendszer.”** Nem: azt jelenti, hogy *pontosan
   mértük*. Egy rossz rendszernek is lehet szűk intervalluma.
4. **„Az intervallum lefedi a jövőbeli valós üzemeket is.”** Nem. Csak a mintavétel ingadozását
   méri *ugyanabból a kérdés- és üzemgenerátorból*. Hogy a szintetikus üzem mennyire hasonlít a
   valódira (külső érvényesség), azt semmilyen CI nem mondja meg — az a Korlátok fejezetbe tartozik.
5. **„Több újrahúzás szűkebb intervallumot ad.”** Nem. A 2000 helyett 20 000 csak a *szimuláció*
   zaját csökkenti; az intervallum szélességét az **adat** mennyisége (kérdések, blokkok száma) adja.

## Ha egyet olvasol

Wikipedia, *Confidence interval* — főleg a „Misunderstandings” szakasz:
https://en.wikipedia.org/wiki/Confidence_interval
