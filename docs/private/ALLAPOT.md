# Állapot — egy pillantásra

**Frissítve: 2026-10-29 (csütörtök).**
Ezt az oldalt a `/log-progress` frissíti minden munkamenet végén. A részletek a heti naplóban vannak
(`50-progress/2026-W44.md`), a mérések a `30-experiments/`-ben, a döntések a `20-decisions/`-ben.

## Egy mondatban

A valósághű generátor (v2) kész; a régi rendszer v2-n gyengébb volt, ezért egy külön megnevezett, hangolt rendszer
(V2T) készült, amely a félretett ellenőrző üzemeken 94,5% / 95,7%-ot ért el a régi 89,0% / 88,3%-ával szemben;
most a lezárt v2-mérések (R4/R5) előkészítése fut.

## Fázisok

| # | Fázis | Állapot |
|---|---|---|
| 1–4b | v1: benchmark, tudásgráf, Q&A, fő kísérlet, egylapos vég | ✔ kész (EXP-0001, EXP-0002; befagyasztva F1 `07d4029`) |
| 6b | Alkalmazás / demó | ✔ kész; v2-rajzjelek `3181573` (10-27) |
| v2 | Valósághű generátor (ADR-0057/0058/0059) | ✔ kész: T0 `0ba680a` … T16 `917b4c3` (10-25 → 10-27) |
| v2-mérés | EXP-0007 (ADR-0060): R0–R3, próba, minőségellenőrzés | ✔ kész (`3f91905`, `133b7f7`, `02af1df`) |
| V2T | Hangolt rendszer (ADR-0061): építés, 3 hangolási kör, ellenőrzés | ✔ kész (`c51c83e`, 10-29) |
| R4/R5 | Lezárt v2-mérések a hangolt rendszerrel (V2T-A) | 🟡 a futtatószkriptek átállítása folyik |
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
| RM-T5 | R4/R5 szkriptek a V2T-A-ra (+ régi rendszer összevetésül, + ContextRAG 1–10 lapon) | 🟡 folyamatban | | 10-29 |
| — | E7 befagyasztás → R4 → R5 | ⬜ következő | | |

## Ellenőrzőpontok a naptárhoz képest

| Pont | Dátum | Mi kell hozzá | Hol tartunk |
|---|---|---|---|
| Leadás | okt. 31. | dolgozat | 🟡 a v2-mérések még futnak; a v1-es eredmények készen állnak |

## Mi vár rád

1. **Az R4/R5 plafonjának jóváhagyása**, ha a szkriptek elkészültek (becslés ≈ $5,6 + $1,5 + $2–3).
2. **A T0–T16 és a V2T átnézése** (a „Generátor v2 – átnézendő változások” dokumentum).
3. **A TDK-ról szóló döntés**; addig a `plantkg` összevonása parkol.

## Mit olvass el legközelebb

Semmit — a következő chat mindent a beszélgetésbe ír le (a chat az egyetlen forrás).
