# Átnézési útmutató — generátor v2 és a hangolt rendszer (V2T)

**Időszak:** `0ba680a` (10-25) … `c51c83e` (10-29), 50 commit. A `src` és a `tests` mappában 295 fájl változott,
33 602 sor került be és 681 ki (`git diff --shortstat 0ba680a^..c51c83e -- src tests`). **Nem kell soronként
elolvasni.** Ugyanaz a módszer, mint a régi útmutatóban (`ATNEZESI-UTMUTATO.md` 2. pont): commit-üzenet → tesztnevek
→ a modul tetején lévő leírás → a fő függvény → futtatás. Amit nem értesz, az a
`50-progress/atnezes-kerdesek.md`-be kerül.

**Hat fejezet, témák szerint.** A–D a generátor, E a mérés eszközei, F a hangolt rendszer. E-t elég átfutni.

---

## A — Miért kell v2, és mit tart meg a v1-ből

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `0ba680a` | a v1 befagyasztása: byte-pontos „golden” kimenetek, rögzített osztálylista | a commit-üzenet + `git show --stat` |
| `3787f3d` | 16 valódi P&ID lap kézi leltára 11 nyilvános forrásból | a leltár táblázata (`10-literature/real-pid-composition-2026-10.md`) |
| `e50a881`, `a24630c` | ADR-0058; `adapters/pydexpi_vocabulary.py` — `derive_vocabulary`; `graph/schema_classes.py` | `derive_vocabulary` alaposan |
| | `tests/test_schema_vocabulary.py`, `tests/v2/test_class_vocabulary.py` | a tesztneveket |

**Tanulójegyzet előtte:** `docs/Notes/valos-pid-felepites.md`.
**Önellenőrzés:** Miért kell a v1-et byte-pontosan befagyasztani, mielőtt v2-t írunk? Mi az „ősök szabálya”
(ancestry rule), amellyel a pyDEXPI osztályaiból a 98 sémaosztály lesz?

## B — Az elemek neve: tagnyelvtan és a terv adatmodellje

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `c538093`, `d18e81b` | `benchmark/v2/tags.py` — `format_equipment_tag`, `format_instrument_tag`; az ISA betűkódok | alaposan (rövid) |
| `5f12bcc` | `benchmark/v2/config.py`, `plan_models.py` | átfutva |
| `7c8d040` | minden v2-paraméter értéke deklarálva (ADR-0059) | a commit-üzenet |
| | `tests/v2/test_generator_v2_tags.py` | alaposan |

**Önellenőrzés:** Mit jelent a `PIC-27008` tag minden betűje és számjegye? Miért kell, hogy minden paraméter
értéke előre le legyen írva?

## C — A DEXPI-építő: vezetékek, szerelvények, műszerek

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `5855934`, `01a5026` | `adapters/pydexpi_builder_v2.py` — `DexpiPlantBuilderV2`; `…_lines.py`, `…_instruments.py` | az osztály docstringje + a vezeték-építés alaposan |
| `9677de0` | `benchmark/v2/trims*.py` — szabványos „trimek” (szivattyú, kompresszor, szabályozószelep, edény) | egy trim alaposan, a többi átfutva |
| `44e27af` | `benchmark/v2/instruments.py` — műszersablonok | átfutva |
| `83a42aa` | `--vocabulary` kapcsoló: az EX01 a saját osztályait tartja meg v2 alatt | a commit-üzenet |
| | `tests/v2/test_dexpi_builder_v2_constructs.py`, `test_dexpi_builder_v2_equivalence.py` | a tesztneveket |

**Tanulójegyzet előtte:** `docs/Notes/pid-jelutak-es-pydexpi-modell.md`.
**Önellenőrzés:** Mi az a „trim”, és miért van egy szabályozószelep mellett két elzáró és egy megkerülő szelep?
Mit ellenőriz az „equivalence” teszt?

## D — Az üzem összerakása: minták, folyamatséma, lapok

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `1acc82d`, `ca8a676` | `benchmark/v2/patterns/` — `pump_set.py` (`build_pump_set`) alaposan, a többi minta átfutva | |
| `13218a3` | `benchmark/v2/flowsheet.py` — `draw_flowsheet`, `wire`; `planner.py` — `plan_plant`; `sheets.py` | alaposan |
| `155017f` | `ingest/headline_v2.py`, a `--headline-v2` kapcsoló | átfutva |
| `917b4c3` | `benchmark/v2/composition.py`, `coverage.py`, az S1–S24 invariánsok, `TEST_SEEDS_V2` | a commit-üzenet + a tesztnevek |
| `3181573` | a demó ISO-rajzjelei | a demóban megnézve |

**Próbáld ki:** `uv run pytest tests/v2/test_first_plant.py -v`
**Önellenőrzés:** Mi a különbség a minta (pattern), a folyamatséma (flowsheet) és a lap között? Miért külön
tartomány (5000–5999) a teszt-seedeké?

## E — A v2-mérés eszközei (átfutva)

`dc19941`, `5eb4266`: kapuk, próba, minőségellenőrzés, futtató szkriptek. `133b7f7`, `02af1df`: mérési rekordok.
Elég a commit-üzeneteket elolvasni. **A lényeg:** a régi rendszer (F1) v2-n 0,896-ot ért el (Cypher 0,595, ágens
0,840), v1-en a Cypher 0,733, az ágens 0,972 volt. Ezért kellett a V2T.

## F — A hangolt rendszer (V2T)

| Commit | Mit nézz meg | Hogyan |
|---|---|---|
| `ebb78a0` | ADR-0061: miért külön nevű, hangolt rendszer, és nem az F1 javítása | alaposan |
| `6eccf2e` | `graph/line_view.py` — `fold_line_edges`: a vezetéknézet átlát a tag nélküli idomokon | alaposan |
| `2d30bb3`, `a38ce0b` | az ágens és az adatbázis is megkapja a vezetéknézetet (`line_to` él) | átfutva |
| `b013a0c` | `qa/strategies/cypher_rag_lines.py` — `CypherRagLines`; `prompts/cypher_query_v2t.txt`; `qa/cypher_guard.py` | a prompt és a javítókör alaposan |
| `ee8e164` | `qa/cascade/policies_v2t/cascade_v4*.json`; `qa/cascade/limits.py` | a két JSON alaposan (rövid) |
| `1c37ea0`, `7ab54fb` | a 2. és 3. hangolási kör: 4–5 sornyi prompt-változás | `git show` — alaposan, tanulságos |
| `c51c83e` | az ellenőrző mérés: 154/163 és 156/163, szemben az F1 145 és 144 eredményével | a futási jegyzet |

**Próbáld ki:** `uv run pytest tests/v2/test_line_view.py tests/v2/test_cascade_v4.py -v`
**Önellenőrzés:** Mi a különbség a `cascade_v4` és a `cascade_v4_iso` között? (Tipp: `start_tier_by_label`.)
Miért nem szabad a hangolást a teszt-seedeken végezni? Mi a „repair round”, és miért csak egy van?

---

## Pipálós lista

- [ ] A — v1-befagyasztás, valódi leltár, szókészlet
- [ ] B — tagnyelvtan, konfiguráció
- [ ] C — DEXPI-építő, trimek, műszerek
- [ ] D — minták, folyamatséma, lapok, invariánsok
- [ ] E — mérőeszközök (átfutva)
- [ ] F — V2T: vezetéknézet, Cypher-szint, kaszkád, hangolási körök
