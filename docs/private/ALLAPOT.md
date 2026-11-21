# Állapot — egy pillantásra

**Frissítve: 2026-11-20 (péntek).**
Ezt az oldalt a `/log-progress` frissíti minden munkamenet végén. A részletek a heti naplóban vannak
(`50-progress/2026-W47.md`), a mérések a `30-experiments/`-ben, a döntések a `20-decisions/`-ben.

## Egy mondatban

Az EXP-0008 tiszta újramérése lefutott és fel van töltve. A kaszkád kb. 100 lapon 0,914, kb. 1000 lapon 0,908
pontosságú, öt-öt üzemen, és kérdésenként alig drágább. A ContextRAG már egy lapon is gyengébb (0,779 a 0,985-tel
szemben). Most az átnézés jön a tanulási térképen, utána a demó v2.

## Fázisok

| # | Fázis | Állapot |
|---|---|---|
| 1–4b | v1: benchmark, tudásgráf, Q&A, fő kísérlet, egylapos vég | ✔ kész (EXP-0001, EXP-0002) |
| v2 | Valósághű generátor (ADR-0057/0058/0059) | ✔ kész: T0 `0ba680a` … T16 `917b4c3` |
| v2-mérés | Első v2 mérés: EXP-0007, EXP-0004 P3/P4 | ✔ kész. Az EXP-0008 felülírta. |
| Kódátnézés | Minden lelet javítása (ADR-0065) | ✔ `60cc516`, `9011ade` (11-08, 11-10) |
| EXP-0008 | Tiszta v2 újramérés, öt-öt üzem skálánként | ✔ `6955036`, `e54546e`, `e54a495` (11-19, push kész) |
| Tanulási térkép | Egy út végig a projekten (artifact) | ✔ `442b684` (11-10). Az EXP-0008-frissítés commitra vár. |
| 6b | Demó | ✔ v1 kész; v2 (ADR-0064) a következő |

## Feladatok (a legutóbbiak)

| Feladat | Mit csinál | Állapot | Commit | Dátum |
|---|---|---|---|---|
| ADR-0065 | Kódátnézés: minden lelet javítva | ✔ | `60cc516`, `9011ade` | 11-08, 11-10 |
| PREREG | Az EXP-0008 előzetes regisztrációja (A és B rész) | ✔ | `ca3a854`, `5d31cbb`, `da7b3eb` | 11-10 – 11-12 |
| G2 | A bíráló próbafutásának javítása | ✔ | `476499d` | 11-11 |
| EXP-0008 | A teljes futás, M0–M10b ($26,56 + $5,23) | ✔ | `e54546e` | 11-19 |
| — | Eltérésnapló, eredményjegyzet, eredménytábla | ✔ | `6955036`, `e54a495` | 11-19 |
| Térkép | EXP-0008-cal frissítve, újra közzétéve | 🟡 kész, commitra vár | | 11-20 |
| — | `readable-py` skill telepítve; az architect/coder/researcher ügynökök visszaállítva | 🟡 kész, commitra vár | | 11-20 |
| Demó v2 | T1–T7 (ADR-0064) | ⬜ | | |

## Ellenőrzőpontok

| Pont | Mi kell hozzá | Hol tartunk |
|---|---|---|
| Végleges mérés | EXP-0008 lefut, commitolva | 🟢 kész, push is |
| Átnézés | A projekt átnézése a térképen | 🟡 most kezdődik |
| Demó v2 | T1–T7 | 🟡 következik |

## Mi vár rád

1. **Átnézés** a tanulási térképen: https://claude.ai/artifact/4B5CtZjxe677rbkqDNTV9b
2. **Döntés:** az eredeti állítás „megfordul” szava nem állja meg a helyét (X1 és X2 FAIL). Hogyan fogalmazzuk át?
3. **Commit**, ha kéred: a térkép frissítése, a `readable-py` skill, a visszaállított ügynökök.

## Mit olvass el legközelebb

1. A tanulási térkép bevezetője és a 10. állomás (Kísérletek időrendben).
2. A 0. állomás új bírálói kérdése a „megfordulásról”.
