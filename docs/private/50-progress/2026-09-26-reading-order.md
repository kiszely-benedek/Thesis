# Mit olvass el — 2026-09-26

Egyelőre minden döntés megszületett. Az alábbiak közül semmi sem akasztja meg a munkát; akkor olvasd, amikor van
energiád, ebben a sorrendben.

**Alap (összesen kb. 30 perc, magyarul):**
1. `docs/Notes/graphrag-lekeresi-strategiak.md` — a négy módszer, ahogy az LLM megkaphatja a gráfot, és mit jelent
   a „crossover”. Ez maga a fő kísérlet.
2. `docs/Notes/entitasfeloldas-es-megoldokulcs.md` — hogyan lesz a lapokból egy üzemgráf, és miért nem láthatja
   az összekötő a megoldókulcsot. Ez a T2–T4 háttere.

**Utána, ha a nagy képet akarod (angolul, 10 perc):**
3. `docs/private/40-design/thesis-phase-plan.md` — csak a §2 (mit állíthatunk) és a §3 (naptár).

**Csak ha érdekel:** a rövid ADR-ek a `docs/private/20-decisions/` mappában (0008–0020, egyenként ~40 sor). A hosszú
eredetiek a `20-decisions/full/` mappában vannak — azokat soha nem kell elolvasnod.

**Most teljesen kihagyhatod:** `kg-construction.md` és `qa-system.md`. Ezek a coder utasításai.

## A ma hozott döntéseid (hogy meglegyenek)
ADR-0009…0017 elfogadva (0012 = K3, nincs RDF); 0018 → **A1** (nincs kitalált berendezés-adat a generált
üzemekben); 0020 = a valódi DEXPI-fájlok megtartják a saját adataikat. Csak P&ID; BSc,
angolul.

## Amit csak te tudsz megcsinálni (nem sürgős — kb. egy héten belül kell)
- Neo4j Desktop 2 → hozz létre egy helyi adatbázist; állítsd be: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`.
- OpenRouter kulcs → `OPENROUTER_API_KEY`.
- Küldd el a BME sablon linkjét.
- Commitold a kész coder-feladatokat a chatben kapott parancsokkal (T1, T2, T3 — ebben a sorrendben).
