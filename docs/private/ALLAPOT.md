# Állapot — egy pillantásra

**Frissítve: 2026-10-23 (péntek).**
Ezt az oldalt a `/log-progress` frissíti minden munkamenet végén. A részletek a heti naplóban vannak
(`50-progress/2026-W43.md`), a mérések a `30-experiments/_results.md`-ben, a döntések a `20-decisions/`-ben.

## Egy mondatban

Minden mérés és a demó kész és commitolva; most a README és az eszköz-/dokumentációs mappák közzététele, utána a
tanulás (a rendszer egészének megértése a védéshez) jön.

## Fázisok

| # | Fázis | Állapot |
|---|---|---|
| 1 | Benchmark (generált üzemek lapokra vágva) | ✔ kész |
| 2 | Tudásgráf-építés (beolvasás → összekötés → Neo4j) | ✔ kész |
| 3 | Q&A rendszer | ✔ kész: cascade_v3 (Cypher → ügynök, Luna), befagyasztva `07d4029` (F1) |
| 4 | Fő kísérlet (~100 és ~1 000 lap) | ✔ kész: lezárt teszt EXP-0002 (H100/H1000), infrastruktúra-költség INFRA-1 |
| 4b | Egylapos vég (EXP-0001) | ✔ kész: méretlétra 1/4/10/30 lap + ChatP&ID EX01 |
| 5 | A lapösszekötő értékelése + Jev (EXP-0004) | ✖ nem fért bele (nem része a mostani munkának) |
| 6b | Alkalmazás / demó | ✔ kész (ADR-0055, ADR-0056: angol nyelvű, mindig élő válasz), utolsó commit `e2b22ad` (10-16) |
| 7 | Dolgozat írása | 🟡 folyamatban |

## Feladatok (a legutóbbiak; a régebbiek a heti naplóban)

| Feladat | Mit csinál | Állapot | Commit | Dátum |
|---|---|---|---|---|
| DP-T1…T4 | Demó: gyorsítótár, lefedettség, adatbázis-állapot, példakérdések | ✔ | `89f8dbe`, `7d4ef78`, `99ca994`, `6986e69` | 10-12 |
| DP-T5 | Demó: hibakódok + felirat-tábla | ✔ | `ce9bb60` | 10-16 |
| ADR-0056 | Demó angolul, mindig élőben | ✔ | `b068363`, `9688c30`, `5fac617` | 10-16 |
| — | Üzemváltás = Neo4j-betöltés; valódi útvonal rögzítése | ✔ | `77a7d84`, `56ab2d9` | 10-16 |
| DP-T6, T7 | Új oldalszerkezet, teljes válaszkártya | ✔ | `e859ebd`, `7d79a75` | 10-16 |
| — | Útvonal-nézet SVG-ben, élő haladásjelző | ✔ | `b012d10`, `4a77315`, `438a59f` | 10-16 |
| DP-T8…T10 | PDF-ugrás, eredmények kiszolgálása, Eredmények fül | ✔ | `799249d`, `b79abd2`, `2c4444c` | 10-16 |
| — | Tagkereső, navigálható válaszok, prezentációs mód | ✔ | `1c16adf`, `172b4c4`, `e2b22ad` | 10-16 |
| — | Valós P&ID-adatok és -összetétel kutatása; mérések időrendben | ✔ (a `docs/`-ban) | — | 10-22 |
| — | README újraírása + eszközök és `docs/` közzététele egy commitban | 🟡 kész, **commitra vár (te futtatod)** | | 10-23 |
| — | Tanulás: nagy kép → benchmark → tudásgráf → Q&A → kísérletek → ADR-ek → kódtérkép | ⬜ következő | | |

## Ellenőrzőpontok a naptárhoz képest

| Pont | Dátum | Mi kell hozzá | Hol tartunk |
|---|---|---|---|
| CP1 | okt. 4. | 2. fázis kész; QA alapok | 🟢 kész |
| CP2 | okt. 11. | Q&A módszerek; pilot; modell rögzítése | 🟢 kész (Luna rögzítve, ADR-0050) |
| CP3 | okt. 17. | ChatP&ID-összevetés; fő kísérlet | 🟢 kész (EXP-0001, EXP-0002) |
| CP4 | okt. 24. | a „ha belefér” tételek; utolsó kísérleti nap | 🟢 a mérések lezárultak, a demó kész |

## Mi vár rád

1. **A commit lefuttatása** (README + eszközök + `docs/`), a parancs a 10-23-i chatben van; előtte a
   `.git/info/exclude` két-három sorát kell törölni (ott is le van írva).
2. **Döntés:** felkerüljenek-e a kiadói cikk-PDF-ek (`docs/Academic_papers/`, 11 MB) a nyilvános repóba.

## Mit olvass el legközelebb

Semmit — a következő chat mindent a beszélgetésbe ír le (a chat az egyetlen forrás).
