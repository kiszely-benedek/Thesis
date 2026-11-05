# Állapot — egy pillantásra

**Frissítve: 2026-11-05 (csütörtök).**
Ezt az oldalt a `/log-progress` frissíti minden munkamenet végén. A részletek a heti naplóban vannak
(`50-progress/2026-W45.md`), a mérések a `30-experiments/`-ben, a döntések a `20-decisions/`-ben.

## Egy mondatban

Az EXP-0004 (ugyanannak a berendezésnek a lapokon eltérően írt azonosítói) fizetős P3 mérése kész, és minden előre
rögzített állítás teljesült: a nyelvi modelles döntő a nem hangolt elnevezési variánsokon 0,983, a szabályalapú 0,347;
most futnak az ingyenes próbafutások a végpontok közötti (kérdés-válasz) mérés költségkorlátjához.

## Fázisok

| # | Fázis | Állapot |
|---|---|---|
| 1–4b | v1: benchmark, tudásgráf, Q&A, fő kísérlet, egylapos vég | ✔ kész (EXP-0001, EXP-0002; befagyasztva F1 `07d4029`) |
| 6b | Alkalmazás / demó | ✔ v1 kész; v2 (kérdéstípus szerinti útválasztás, H1000g2 üzem) tervezve: ADR-0064 `9bc93d5` |
| v2 | Valósághű generátor (ADR-0057/0058/0059) | ✔ kész: T0 `0ba680a` … T16 `917b4c3` |
| v2-mérés | EXP-0007: hangolt rendszer V2T-A, R4, R5, INFRA-2 | ✔ kész (`87eb79e`, `92ae22e`, `fe48a3e`) |
| EXP-0004 | Tag-variánsok azonosítása lapok között (ADR-0063) | 🟡 P3 kész (`1ad5d99`); P4 próbafutás fut |
| 7 | Dolgozat írása | ⬜ később indul |

## Feladatok (a legutóbbiak)

| Feladat | Mit csinál | Állapot | Commit | Dátum |
|---|---|---|---|---|
| — | R5 maradéka + INFRA-2 | ✔ | `92ae22e`, `fe48a3e` | 11-04 |
| X-T1…X-T4 | Variáns-generátor, blokkolás, döntők, bekötés | ✔ | `4a84530`, `7e5cc1c`, `aa1e25c`, `226aacd` | 11-04 |
| — | E8 befagyasztás, előzetes regisztráció | ✔ | `8c38b16`, `c6099fc` | 11-04 |
| X-T5, X-T6 | EXP-0004 csomag, nyelvi modelles döntő (D4) | ✔ | `a8c791c`, `67a38f9` | 11-04 |
| P3 | Fizetős mérés a négy tesztüzemen | ✔ | `1ad5d99` | 11-05 |
| — | ADR-0049, ADR-0062, ADR-0064 elfogadva, újdonság-ellenőrzés | ✔ | `9bc93d5` | 11-05 |
| X-T7 | Végpontok közötti mérés futtatója | ✔ | `37bee83` | 11-05 |
| P4 próba | Ingyenes próbafutás D0, D2, D4 karra | 🟡 fut (17:44-től, kb. 3 óra) | | 11-05 |
| P4 | Fizetős végpontok közötti mérés | ⬜ jóváhagyásra vár | | |
| X-T8 | E2E jelentés, futási jegyzet, eredménytábla | ⬜ | | |
| Demó v2 | T1–T7 | ⬜ | | |

## Ellenőrzőpontok

| Pont | Mi kell hozzá | Hol tartunk |
|---|---|---|
| EXP-0004 lezárva | P4 + X-T8 | 🟡 a próbafutás megy, utána fizetős P4 |
| „Végleges” kód | X-T8 commitolva, eredménytábla teljes, tesztek zöldek | 🟡 az EXP-0004 és a demó v2 van hátra |

## Mi vár rád

1. **A P4 költségkorlátjának jóváhagyása**, amikor a próbafutások végeztek (legfeljebb $4,44).
2. **A commitok** a chatben megadott parancsokkal (napló, index, állapotoldal).

## Mit olvass el legközelebb

Semmit külön — a chat mindent leír (a chat az egyetlen forrás).
