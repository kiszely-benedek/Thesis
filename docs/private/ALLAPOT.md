# Állapot — egy pillantásra

**Frissítve: 2026-11-27 (péntek).**
Ezt az oldalt a `/log-progress` frissíti minden munkamenet végén. A részletek a heti naplóban vannak
(`50-progress/2026-W48.md`), a mérések a `30-experiments/`-ben, a döntések a `20-decisions/`-ben.

## Egy mondatban

Az EXP-0009 teljesen lefutott a kézikönyvi szabályokkal épült v2.2-es üzemeken. A fő állítás (Q4) áll: az A2
100 lapon 0,899, 1000 lapon 0,913 pontos. A K1 ismét megbukott: a „mindig ügynök” pontosabb a kaszkádnál.
A B rendszer (feltáró) jól olvassa a szelepállást (0,96), de a leválasztási kérdések mindkét rendszernek nehezek.

## Fázisok

| # | Fázis | Állapot |
|---|---|---|
| 1–4b | v1: benchmark, tudásgráf, Q&A, fő kísérlet, egylapos vég | ✔ kész (EXP-0001, EXP-0002) |
| v2 | Valósághű generátor (ADR-0057/0058/0059) | ✔ kész: T0 `0ba680a` … T16 `917b4c3` |
| Kódátnézés | Minden lelet javítása (ADR-0065) | ✔ `60cc516`, `9011ade` (11-08, 11-10) |
| EXP-0008 | Tiszta v2 újramérés, öt-öt üzem skálánként | ✔ `6955036`, `e54546e`, `e54a495` (11-19) |
| 6b | Demó | ✔ v1 kész; v2 (ADR-0064) kész: `a39bdb1`, `5546d29`, `321fe3b` (11-21) |
| v2.2 | Kézikönyvi szabályokra épülő generátor és a V2T-B rendszer | ✔ `d8914f8` … `871aee5`, hangolás `91c1139` (11-23 – 11-25) |
| EXP-0009 | Lezárt mérés v2.2-es üzemeken, A2 és B, GLM-ág, audit | ✔ lefutott 11-27; befagyasztás `36d619f`, eltérés `b3b63a5`; eredmények `cfa839f`, `9728ae8` |

## Feladatok (a legutóbbiak)

| Feladat | Mit csinál | Állapot | Commit | Dátum |
|---|---|---|---|---|
| v2.2 T6–T17 | Kézikönyvi szabályok, hálózatok, X-családok, elemzés | ✔ | `d8914f8` … `871aee5` | 11-23 – 11-24 |
| Gold-ellenőrzés | Független ellenőrzés: 14 296 kérdés, 0 eltérés | ✔ | `3a935dd` | 11-24 |
| B hangolás | Két kör, a második javítva | ✔ | `d499256`, `91c1139` | 11-25 |
| E10 + PREREG B | Befagyasztás a lezárt üzemek előtt | ✔ | `36d619f` | 11-25 |
| Eltérés | B feltáró ágként fut (G1-B bukott) | ✔ | `b3b63a5` | 11-25 |
| EXP-0009 | Teljes futás, P0–END ($19,58 + $3,51) | ✔ | `cfa839f` | 11-27 |
| Audit | 25 eltérés besorolva: 0 pontozóhiba | ✔ | `cfa839f` | 11-27 |
| Eredményjegyzet | `30-experiments/EXP-0009-v22-sealed.md` | ✔ | `9728ae8` |
| Szúrópróba | 48 kérdés + 500 leválasztási kérdés ellenőrizve | ✔ | ez a commit | 11-27 |

## Ellenőrzőpontok

| Pont | Mi kell hozzá | Hol tartunk |
|---|---|---|
| EXP-0009 | Lefut, besorolva, commitolva | 🟢 kész |
| Szúrópróba | Nagyobb minta minden kérdéscsaládból a felhasználónak | 🟢 kész: 48 kérdés, 0 hibás helyes válasz; 500 leválasztási kérdés, 0 eltérés |
| Dolgozatterv | A felhasználó mintatervet küld, Claude segít | 🟡 a mintára vár |

## Mi vár rád

1. **Dolgozatterv-minta** elküldése, amikor kész vagy vele.
2. **Döntés (nem sürgős):** megnézessük-e, mennyit számít a leválasztási definíció (üzemanyaggáz-ág) a gyenge
   leválasztási eredményekben.

## Mit olvass el legközelebb

1. Az EXP-0009 eredményei a chatben (11-27).
2. A tanulási térkép bevezetője: https://claude.ai/artifact/4B5CtZjxe677rbkqDNTV9b
