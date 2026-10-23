# Átnézési útmutató — minden, ami az `a5cf586` óta történt

**Cél:** hogy magabiztosan értsd és el tudd magyarázni a kódot és a döntéseket — a dolgozathoz és a védéshez.
**Mennyiség:** 22 commit, 133 fájl, kb. 13 700 új sor (`git diff --shortstat a5cf586^..HEAD`), plusz a `docs/`
dokumentumai. **Nem kell soronként elolvasnod.** Ez az útmutató megmondja, mit nézz alaposan, mit elég átfutni, és
mit hagyhatsz ki.

**Javasolt tempó (becslés, nem mérés):** 6 alkalom, egyenként kb. 1–1,5 óra — alkalmanként egy fejezet (A–F).
Minden fejezet után beszéljük át együtt, amit nem értettél.

---

## 1. Eszközök — hogyan nézd meg a változásokat

**A kód változásai a gitben vannak.** Parancssorban (a repó mappájában):

| Mit akarsz | Parancs |
|---|---|
| Az összes commit listája, sorrendben | `git log --oneline --reverse a5cf586^..HEAD` |
| Egy commit üzenete és a fájljai | `git show --stat <hash>` |
| Egy commit teljes változása (mi került be, mi ki) | `git show <hash>` |
| Egy fájl teljes változása az egész időszakra | `git diff a5cf586^..HEAD -- <fájl>` |
| Egy fájl mostani állapota | egyszerűen nyisd meg a VS Code-ban |

**VS Code-ban kényelmesebb:** bal oldalt a *Source Control* panelen lent a *Graph* nézetben kattints egy commitra
— megmutatja a fájljait, és egy fájlra kattintva a változást kétoldalt (piros = kivett, zöld = új).

**Egy teszt futtatása** (látod, mit ellenőriz és hogy zöld-e):
```
uv run pytest tests/test_resolution_resolver.py -v
```
A `-v` minden teszt nevét kiírja — a nevek mondatok, pl. `test_localized_output_passes_contract`.

**A dokumentumok változásai NEM a gitben vannak** — a `docs/`, `CLAUDE.md` és `.claude/` csak helyben él (így
döntöttél a 2026-09-19-i történet-átírásnál). Ezeknél a lenti listát használd (6. pont).

---

## 2. A módszer — minden commitnál ugyanez az 5 lépés

1. **Olvasd el a commit-üzenetet** (`git show --stat <hash>`). Megmondja, *mit* és *miért*.
2. **Nyisd meg előbb a tesztfájlt, ne a kódot.** A tesztek nevei és kommentjei megmondják, mit *ígér* a kód.
   Ez a leggyorsabb út a megértéshez.
3. **Olvasd el a fő modul tetején lévő leírást** (a docstringet, a `"""…"""` közti szöveget). Minden modul
   elején le van írva, mit csinál és miért.
4. **Nézd meg a fő függvényt** — a fejezeteknél megadom, melyiket. A segédfüggvényeket elég átfutni.
5. **Futtasd le** a tesztet vagy a megadott parancsot, és nézd meg, mit ír ki.

Minden commit után tedd fel magadnak a fejezet végén lévő **önellenőrző kérdéseket**. Amire nem tudsz válaszolni,
azt írd fel a `docs/private/50-progress/atnezes-kerdesek.md` fájlba — azokat együtt átbeszéljük.

---

## 3. A sorrend — hat fejezet

A commitok nem a legkönnyebben érthető sorrendben születtek, ezért **témák szerint** haladunk.

### A fejezet — Rajzból lap: a DEXPI-beolvasó

**Miről szól:** egy valódi P&ID-fájl (DEXPI, az EX01) beolvasása ugyanabba a formába, amibe a generált lapjaink
kerülnek; semmi nem vész el csendben.

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `a5cf586` | `src/plantgraph/adapters/pydexpi_proteus_import.py` — `import_proteus_sheet` | alaposan |
| `271cdf1` (csak az adapter-rész) | `src/plantgraph/adapters/pydexpi_generic.py` — `classify`, és a `GenericItem` a `graph/schema.py`-ban | alaposan |
| | `tests/test_proteus_import.py`, `tests/test_pydexpi_generic.py` | a tesztneveket |

**Próbáld ki:**
```
uv run python -m plantgraph.ingest proteus data/external/C01V04-VER.EX01.xml --no-neo4j
```
(A `counts` részben `n_nodes: 38` áll: az EX01 36 alkatrésze, plusz egy „lap” és egy „korpusz” csomópont, ahogy
az adatbázisba kerülne; `n_unresolved: 2` — az EX01 két lapközi csatlakozóján nincs felirat.)

**Dokumentumok:** ADR-0008 (a DEXPI rajznak számít), ADR-0009 (a bemenet a lapgráf), ADR-0016 (ismeretlen elemek),
ADR-0021 (nincs adatlapadat).

**Önellenőrző kérdések:**
- Mi a DEXPI-fájl, és miben más, mint egy beszkennelt rajz?
- Miért baj, ha egy ismeretlen alkatrész (pl. csőelágazás) csendben kiesik? (Tipp: a T4750 → P4712 útvonal.)
- Mit jelent a `GenericItem`, és mit tart meg egy ismeretlen elemből?
- A ChatP&ID szerint az EX01 212 csomópontból 53-ra sűrűsödik, nálunk 36-ra. Mit tudunk erről, és mit nem?

---

### B fejezet — Sok lapból egy üzem: az összekötés

**Előtte olvasd el:** `docs/Notes/entitasfeloldas-es-megoldokulcs.md` (magyar, ~15 perc). Enélkül ez a fejezet nehéz.

**Miről szól:** a lapokat a rajzon látható feliratok alapján kötjük össze — úgy, hogy a program **ne lássa a
megoldókulcsot**; aztán megmérjük, mennyire jól csinálja.

| Commit | Mit nézz meg (ebben a sorrendben) | Hogyan |
|---|---|---|
| `5481943` | `resolution/localize.py` (új azonosítók minden lapon), `resolution/contract.py` (a „szerződés”) | alaposan |
| `3c97587` | `resolution/connector_labels.py`, `resolution/pairing.py` — `pair_connectors` | alaposan |
| `271cdf1` | `resolution/identity.py`, `merge.py`, `resolver.py` — `resolve`; `eval/graph_equality.py` | a `resolve` alaposan, a többi átfutva |
| `cdc3512` | `eval/resolution_scoring.py` — `score_connector_pairs` | átfutva |
| | `tests/test_resolution_resolver.py` (a G1/G2/G4 kapuk), `tests/test_resolution_imports.py` | alaposan |

**Próbáld ki:**
```
uv run pytest tests/test_resolution_resolver.py -v
uv run python -m plantgraph.ingest synthetic --n-units 50 --budget 16 --check --no-neo4j
```
(A második végén `"gate_equal": true` — a lapokból visszaépített üzem pontosan az eredeti.)

**Dokumentumok:** ADR-0010 (miért korán a resolver, és miért később az értékelése).

**Önellenőrző kérdések:**
- Mi volt a két „szivárgás” (a megoldókulcs két helye), és hogyan zártuk el őket?
- Mit ellenőriz a G1 és a G2 kapu? Miért nem „eredmény”, hogy az alapbeállításon 100%?
- Mit jelent a precision és a recall? Miért lett a recall 0, amikor a tagek kicsit eltérnek a lapokon?
- Miért nem importálhatja a `resolution/` mappa a megoldókulcsot, és melyik teszt figyeli ezt?

---

### C fejezet — A lapolás hibája és javítása

**Miről szól:** kiderült, hogy a lapokra vágás szinte véletlenszerű volt; megtaláltuk az okát és javítottuk.
**Ez jó történet a dolgozatba** (mérés → hiba → ok → javítás → újramérés).

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `1731fae` | `benchmark/strategies.py` — a `_flow_order` függvény | alaposan (rövid) |
| | `tests/test_strategies.py` — az utolsó két teszt | alaposan |

**Próbáld ki** (kb. 15 mp): a lapkeret 16, figyeld a `n_sheets` és `n_connector_pairs` számot:
```
uv run python -m plantgraph.benchmark.scale_smoke --n-units 1000 --budget 16 --seed 0 --no-memory
```

**Dokumentumok:** ADR-0017, `30-experiments/2026-09-26-smoke-06-density.md` (a javítás előtti és utáni táblázat).

**Önellenőrző kérdések:**
- Mi a különbség a szélességi és a mélységi bejárás között, és miért rontotta el a szélességi a lapokat?
- Miért kellett egy második, „közvetlen” teszt is, amikor az első („kevesebbet vág, mint a véletlen”) már megvolt?
- Mit jelent a 42,9 csomópont/lap és a 9,1 csatlakozó/lap, és mihez hasonlítjuk őket?

---

### D fejezet — Betöltés a Neo4j-be, egy paranccsal

**Miről szól:** az összekötött lapokat betöltjük az adatbázisba, ellenőrizzük a számokat; az egészet egy parancs
futtatja végig.

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `a94b6e6` | `store/neo4j_plan.py` — `build_load_plan`; `store/neo4j_rows.py` átfutva | alaposan a tervet |
| `1adc2dc` | `store/neo4j_settings.py` (honnan jön a jelszó), `store/neo4j_loader.py` — `load_corpus` | alaposan |
| `a634491` | `ingest/pipeline.py` — `run_synthetic`; `ingest/__main__.py` (a parancs kapcsolói) | alaposan |
| `e91ac33` | `store/neo4j_probe.py` (gyors ellenőrzés, fut-e az adatbázis) | átfutva |

**Próbáld ki** (előtte indítsd el a Neo4j-t a Desktopban):
```
uv run python -m plantgraph.ingest synthetic --n-units 50 --budget 16 --check --corpus-id probam
```
Utána a Neo4j Browserben: `MATCH (n {corpus_id: "probam"}) RETURN n LIMIT 50`

**Dokumentumok:** `30-experiments/2026-09-26-smoke-04-05-ingest-and-neo4j.md` (1 004 lap, 24,7 mp), ADR-0012 (miért
nincs RDF).

**Önellenőrző kérdések:**
- Miért kerül minden érték *paraméterként* a lekérdezésbe, és miért nem írjuk bele közvetlenül a szövegbe?
- Mi a K-NEO határ (600 mp), és miért rögzítettük *a mérés előtt*?
- Honnan olvassa a program a jelszót, és miért nem kerülhet a gitbe?

---

### E fejezet — A kérdés-válasz rendszer alapjai

**Előtte olvasd el:** `docs/Notes/graphrag-lekeresi-strategiak.md` (magyar, ~15 perc).

**Miről szól:** a nyelvi modell hívása (biztonságosan, visszajátszhatóan), a válaszok pontozása, a közös
válaszlépés, a gráf szöveggé alakítása, és a kérdésgenerátor első fele.

| Commit | Mit nézz meg (ebben a sorrendben) | Hogyan |
|---|---|---|
| `083c7a6` | `qa/prompts/final_answer.txt` — **ezt a szöveget kapja a modell** | alaposan (rövid) |
| `2b12dc5` | `qa/models.py` (kérdés, válasz, eredmény), `qa/scoring.py` — `score_answer` | alaposan |
| `083c7a6` | `qa/final_answer.py` — `run_final_step`; `qa/fit.py` — `check_fit` | alaposan |
| `d48208b` | `llm/models.py`, `llm/cache.py` (a gyorsítótár kulcsa) | átfutva |
| `64c56d5` | `llm/client.py` — a biztonsági zár (`allow_network`) | a zárat alaposan |
| `b0224e5` | `qa/graph_view.py`, `qa/serialize.py` | átfutva |
| `7788442` | `ingest/pipeline.py` — `build_synthetic_corpus`; `qa/corpus.py` (a „gold” fiók) | átfutva |
| `7b8845d` | `qa/questions/evidence.py` (a **k** kiszámítása), `qa/questions/families_flow.py` | alaposan |
| | `tests/qa_toy_plant.py` — kézzel felrajzolt kis üzem; `tests/test_qa_questions_families.py` | alaposan |

**Próbáld ki:**
```
uv run pytest tests/test_qa_questions_families.py -v
uv run pytest tests/test_llm_client.py -v -k "allow_network or key"
```

**Dokumentumok:** ADR-0013 (hogyan pontozunk), ADR-0014 (mely modellek, reprodukálhatóság), ADR-0015 (a fő kísérlet),
**ADR-0022 (döntened kell róla)**.

**Önellenőrző kérdések:**
- Mi a **k**, és miért ez a fő kísérlet legfontosabb változója?
- Miért *számítjuk* ki a helyes választ, és miért nem egy másik nyelvi modell dönti el, hogy jó-e?
- Mire jó a gyorsítótár, és mit jelent, hogy egy futás „visszajátszható”?
- Miért nem elég, hogy a kulcs benne van a `.env`-ben, egy fizetős híváshoz?
- Mi a „kontextusfal”, és mi történik, ha egy kérdés nem fér bele?

---

### F fejezet — Rendrakás (gyors, kb. 15 perc)

| Commit | Mit | Hogyan |
|---|---|---|
| `d9c2c60`, `38c70ed`, `983ea58` | `.gitignore`: mi nem kerül a GitHubra (EX01, `.env`, generált adatok) | `git show <hash>` — néhány sor |
| `fe9f4d8` | minden komment angolra fordítva — **csak szöveg változott**, gépileg ellenőrizve | egy fájlba nézz bele: `git show fe9f4d8 -- src/plantgraph/benchmark/rejoin.py` |
| `c3755bb` | a maradék magyar szöveg (tesztüzenetek, súgó, OPEN100-megjegyzések) | egy példa elég |

**Önellenőrző kérdés:** miért van a `.env` a `.gitignore`-ban, és mi lenne, ha nem lenne?

---

## 4. Amit nyugodtan kihagyhatsz

- A **fordítási commitok** (`fe9f4d8`, `c3755bb`) részleteit — gépileg igazoltuk, hogy a kód nem változott.
- A `20-decisions/full/` mappát — a rövid ADR-ek ugyanazt mondják.
- A `40-design/kg-construction.md` és `qa-system.md` nagy részét — ezek a coder utasításai. Csak a fent megnevezett
  részeket, ha kíváncsi vagy.
- A tesztfájlok belsejének minden sorát — a tesztnevek és a kommentek elegendők.

---

## 5. Pipálós lista

**Kód**
- [ ] A — `a5cf586` DEXPI-beolvasó
- [ ] A — `271cdf1` ismeretlen elemek (`pydexpi_generic.py`)
- [ ] B — `5481943` megoldókulcs elrejtése
- [ ] B — `3c97587` csatlakozók párosítása
- [ ] B — `271cdf1` összevonás, `resolve`, kapuk
- [ ] B — `cdc3512` pontozás
- [ ] C — `1731fae` mélységi lapolás
- [ ] D — `a94b6e6` betöltési terv
- [ ] D — `1adc2dc` betöltés, beállítások
- [ ] D — `a634491` `ingest` parancs
- [ ] D — `e91ac33` gyors kihagyás
- [ ] E — `083c7a6` prompt, közös válaszlépés, fit
- [ ] E — `2b12dc5` Q&A adatmodell, pontozás
- [ ] E — `d48208b` gyorsítótár
- [ ] E — `64c56d5` OpenRouter-kliens
- [ ] E — `b0224e5` gráfnézet, szöveggé alakítás
- [ ] E — `7788442` közös építési út
- [ ] E — `7b8845d` kérdésgenerátor, k
- [ ] F — `.gitignore` commitok, fordítások

**Dokumentumok** (6. pont)
- [ ] A két magyar tanulójegyzet
- [ ] ADR-0008 … 0022 (rövidek)
- [ ] A két mérési jegyzet (SMOKE-06, SMOKE-04/05)
- [ ] A terv §2–§3 és az `ALLAPOT.md`

---

## 6. A dokumentumok, amik ebben az időszakban készültek vagy változtak

Ezek **nincsenek a gitben**, ezért itt a lista — fontossági sorrendben.

| Dokumentum | Mi ez | Olvasd? |
|---|---|---|
| `docs/private/ALLAPOT.md` | az állapot-oldal | **igen** |
| `docs/Notes/graphrag-lekeresi-strategiak.md` | tanulójegyzet: a négy válaszadási módszer | **igen**, E előtt |
| `docs/Notes/entitasfeloldas-es-megoldokulcs.md` | tanulójegyzet: összekötés, megoldókulcs | **igen**, B előtt |
| `docs/private/20-decisions/ADR-0008` … `ADR-0022` | minden döntés, egyenként ~40 sor | **igen**, a fejezeteknél |
| `docs/private/30-experiments/2026-09-26-smoke-06-density.md` | a lapolás javítása, számokkal | igen, C-nél |
| `docs/private/30-experiments/2026-09-26-smoke-04-05-ingest-and-neo4j.md` | betöltés és összekötés nagy méretben | igen, D-nél |
| `docs/private/30-experiments/_results.md` | minden mérés egy táblában | átfutva |
| `docs/private/40-design/thesis-phase-plan.md` | a terv: §2 (mit állíthatunk), §3 (naptár) | csak ez a két rész |
| `docs/private/10-literature/_novelty-log.md` | az újdonság-ellenőrzés, utolsó bejegyzés (2026-09-26) | átfutva |
| `docs/private/50-progress/2026-W39.md` | a heti napló | ha kíváncsi vagy |
| `docs/private/00-index.md` | a projekt térképe | átfutva |
| `docs/private/40-design/kg-construction.md`, `qa-system.md`, `splitter.md` | a coder utasításai | csak a fent jelzett részek |
| `CLAUDE.md`, `.claude/agents/coder.md`, `.claude/skills/log-progress/SKILL.md` | a munkaszabályok változásai (BSc, angol kommentek, állapot-oldal) | elég tudni róla |
| `docs/Academic_papers/2603.22528-ChatPID.pdf` | a ChatP&ID cikk; a 19 kérdés a 28–36. oldalon | a kérdéseket érdemes |
