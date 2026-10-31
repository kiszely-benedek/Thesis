# Állapot — egy pillantásra

**Frissítve: 2026-10-31 (szombat).**
Ezt az oldalt a `/log-progress` frissíti minden munkamenet végén. A részletek a heti naplóban vannak
(`50-progress/2026-W44.md`), a mérések a `30-experiments/`-ben, a döntések a `20-decisions/`-ben.

## Egy mondatban

Az R5 (lezárt v2-teszt a hangolt V2T-A rendszerrel) fő része kész: a fő rendszer 0,911 (100 lap) és 0,891
(1 000 lap), a fő állítás (Q4: a pontosság nem romlik a méretezéssel) teljesül; a gyenge pont az elzárási kérdések
(a hangoláskor nem látott típusokon 0,740); a leíró mérések és a régi rendszerrel való összevetés még futnak.

## Fázisok

| # | Fázis | Állapot |
|---|---|---|
| 1–4b | v1: benchmark, tudásgráf, Q&A, fő kísérlet, egylapos vég | ✔ kész (EXP-0001, EXP-0002; befagyasztva F1 `07d4029`) |
| 6b | Alkalmazás / demó | ✔ kész; v2-rajzjelek `3181573` (10-27) |
| v2 | Valósághű generátor (ADR-0057/0058/0059) | ✔ kész: T0 `0ba680a` … T16 `917b4c3` (10-25 → 10-27) |
| v2-mérés | EXP-0007 (ADR-0060): R0–R3, próba, minőségellenőrzés | ✔ kész (`3f91905`, `133b7f7`, `02af1df`) |
| V2T | Hangolt rendszer (ADR-0061): építés, 3 hangolási kör, ellenőrzés | ✔ kész (`c51c83e`, 10-29) |
| R4/R5 | Lezárt v2-mérések a hangolt rendszerrel (V2T-A) | 🟡 E7, R4 kész (`fdad31f`, `87eb79e`); R5 fő része kész, a többi fut |
| 7 | Dolgozat írása | 🟡 folyamatban |

## Feladatok (a legutóbbiak)

| Feladat | Mit csinál | Állapot | Commit | Dátum |
|---|---|---|---|---|
| T0–T16 | Generátor v2 | ✔ | `0ba680a` … `917b4c3` | 10-25 → 10-27 |
| RM-T1…T4 | Mérőeszközök a v2-mérésekhez | ✔ | `dc19941`, `5eb4266` | 10-27 |
| — | Próba + minőségellenőrzés a régi rendszerrel (D100g2) | ✔ | `133b7f7`, `02af1df` | 10-27 |
| QT-0…QT-7 | Hangolt rendszer (V2T) megépítése | ✔ | `6eccf2e` … `c6260dc` | 10-28 |
| — | 3 hangolási kör (X100g2s211) | ✔ | `785316e`, `e478c24`, `59c7eb9` | 10-28 |
| — | Ellenőrző mérés (X100g2s212, X1000g2s213) | ✔ | `c51c83e` | 10-29 |
| RM-T5 | R4/R5 szkriptek a V2T-A-ra (+ régi rendszer összevetésül, + ContextRAG 1–10 lapon) | ✔ | `fdad31f` | 10-29 |
| — | E7 befagyasztás + R4 tesztkészlet | ✔ | `d72e3b5` | 10-29 |
| — | R4 (létra) | ✔ | `87eb79e` | 10-29 |
| — | R5 kérdésgenerálás javítása (ADR-0062) | ✔ | `28ba910` | 10-31 |
| — | R5 tesztkészlet, futási sorrend, költségkorlát-emelés | ✔ | `f3c0c00`, `aeb2801`, `c77441d`, `59b084d` | 10-31 |
| — | R5 fő mérés (H100g2, H1000g2) | ✔ mérve, a futás adatai még nincsenek commitolva | | 10-31 |
| — | R5 leíró mérések (d0, d50, C1) + régi rendszer (F1) | 🟡 fut | | 10-31 |

## Ellenőrzőpontok

| Pont | Mi kell hozzá | Hol tartunk |
|---|---|---|
| R5 lezárva | minden lépés lefut, jelentések, futási jegyzet | 🟡 a fő rész kész, a többi néhány óra |

## Mi vár rád

1. **Az R5 tanulási jegyzetének átolvasása** (`docs/Notes/lezart-teszt-eredmenyek-olvasasa.md`), a lényege a chatben.
2. **A commitok** a chatben megadott parancsokkal (jegyzet, napló, állapotoldal; az R5 adatai a futás végén).
3. **A T0–T16 és a V2T átnézése** (a „Generátor v2 – átnézendő változások” dokumentum).

## Mit olvass el legközelebb

Semmit külön — a chat mindent leír (a chat az egyetlen forrás).
