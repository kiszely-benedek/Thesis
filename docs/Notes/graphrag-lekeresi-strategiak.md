---
topic: GraphRAG lekérési stratégiák (ContextRAG, VectorRAG, PathRAG, CypherRAG) és a "crossover"
status: draft
related: [ADR-0001, ADR-0010, ADR-0013, ADR-0014, docs/private/40-design/thesis-phase-plan.md, docs/private/10-literature/2603.22528.md, lpg-vs-rdf.md]
---

# GraphRAG lekérési stratégiák és a "crossover"

## Miért létezik

Egy nyelvi modell (LLM) semmit sem tud a te üzemedről. Ha megkérdezed, „melyik szivattyú táplálja a
T-101 tartályt?", csak akkor válaszolhat helyesen, ha a kérdéssel együtt **megkapja a releváns tényeket**. A
RAG (*retrieval-augmented generation*, lekéréssel kiegészített generálás) ezt a problémát oldja meg: a válasz
előtt **kikeresi** a tudásbázisból azt, ami a kérdéshez kell, és azt teszi a promptba.

A GraphRAG ugyanez, csak a tudásbázis **gráf** (csomópontok és élek), nem szövegdarabok halmaza. A P&ID
eleve gráf — berendezések, szelepek, csővezetékek és a köztük lévő kapcsolatok —, ezért kézenfekvő.

A kulcskérdés mindig ugyanaz: **hogyan jut el a gráf releváns része a modellhez?** Erre négy válasz van, és
ezek közül a ChatP&ID cikk (`2603.22528`) azt találta, hogy egyetlen lapon a *legbutább* nyer.

## Az alapötlet — a négy stratégia

| Stratégia | Mit tesz a promptba? | Hasonlat |
|---|---|---|
| **ContextRAG** | **az egész** (összevont) gráfot, GraphML szövegként. Nincs lekérés. | Odaadod a teljes rajzot. |
| **VectorRAG** | a kérdéshez **szemantikailag leghasonlóbb** *k* csomópont leírását (embedding + koszinusz-hasonlóság) | Kulcsszó szerint kikeresel pár cetlit. |
| **PathRAG** | vektoros kereséssel talált kiinduló csomópontból az LLM **lépésenként bejárja** a szomszédokat (a cikkben max. 2 szélesség, 3 mélység) | Ujjal végigkövetsz egy vezetéket. |
| **CypherRAG** | az LLM a kérdést **Cypher lekérdezéssé** fordítja, a Neo4j lefuttatja, az eredmény megy a promptba | Adatbázis-lekérdezést írsz. |

A cikk eredményei egy lapon (GPT-5-mini, konceptuális gráf): **ContextRAG 0.91**, CypherRAG 0.86, PathRAG
0.83, VectorRAG 0.82. Miért nyer a „butaság"? Mert a lap gráfja kicsi — **212 csomópont, összevonva 53** —,
és ha a modell *mindent* lát, nem tud rosszul keresni. A lekérés csak akkor ér valamit, ha a teljes gráf nem
fér el, vagy túl nagy ahhoz, hogy a modell jól figyeljen rá.

**A crossover** (keresztezési pont) az a korpuszméret, ahol a rangsor megfordul: ahol egy lekérő stratégia
először lesz jobb, mint a ContextRAG. A dolgozat P4 fázisa (EXP-0002) ezt méri, a lapszámot 1-től ezrekig
növelve.

**A kemény fal.** Minden modellnek van **kontextusablaka** — egy maximális tokenszám, amit egyszerre be tud
olvasni. Ha a sorosított gráf ennél nagyobb, a ContextRAG **nem romlik, hanem egyszerűen nem futtatható**.
Ez nem a pontosság lassú csökkenése, hanem egy fal. Ezért az ADR-0014 szerint a válaszoló modellt a mérés
elején rögzíteni kell: a fal helye a modelltől függ, tehát kísérleti változó.

## Kidolgozott példa — mekkora lenne a ContextRAG promptja?

A saját generátorunkkal előállított üzemeket GraphML-lé sorosítottam, ahogy a ContextRAG tenné, és megszámoltam
a karaktereket. Futtatva 2026-09-25-én, `seed=0`, a repó `.venv`-jében:

```python
import networkx as nx
from plantgraph.adapters.pydexpi_adapter import plant_graph
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.benchmark.generator_models import GeneratorConfig

def graphml_chars(graph: nx.DiGraph) -> int:
    clean = nx.DiGraph()   # a GraphML csak egyszerű attribútumtípusokat enged, ezért mindent str-ré alakítunk
    clean.add_nodes_from((n, {k: str(v) for k, v in d.items()}) for n, d in graph.nodes(data=True))
    clean.add_edges_from((u, v, {k: str(x) for k, x in d.items()}) for u, v, d in graph.edges(data=True))
    return len("\n".join(nx.generate_graphml(clean)))

for n_units in (1, 4, 50, 1000):
    plant, _ = plant_graph(generate_plant(GeneratorConfig(seed=0, n_units=n_units)))
    print(n_units, plant.number_of_nodes(), plant.number_of_edges(), graphml_chars(plant))
```

Mért kimenet:

| `n_units` | csomópont | él | GraphML karakter |
|---:|---:|---:|---:|
| 1 | 13 | 13 | 5,829 |
| 4 | 67 | 75 | 27,769 |
| 50 | 739 | 816 | 296,943 |
| 1,000 | 14,687 | 16,171 | 5,990,747 |

(A 14,687 csomópont egyezik a SMOKE-01 mérésével, tehát ugyanazt a gráfot sorosítottuk.)

Mit olvass ki belőle? A prompt mérete **lineárisan nő** a gráffal — kb. 400 karakter csomópontonként ebben a
mintában. Hogy ez **hány token**, azt csak a választott modell tokenizálója mondja meg; ezt szándékosan nem
becsültem meg fejből. A lényeg így is látszik: a legnagyobb méretnél már **közel hatmillió karakter** — ez
nagyságrendekkel több, mint amit egy lapnyi, 53 csomópontos gráf igényelt a cikkben. Valahol a táblázat két
sora között van a fal; hogy pontosan hol, az a P3 pilotjának az egyik első mérése lesz.

## Hol illeszkedik (és hol nem)

- **P3 (Q&A rendszer):** mind a négy stratégiát meg kell építenünk a saját gráfunk fölött, és egy lapon
  (EXP-0001) reprodukálni a cikk **rangsorát** — nem a harmadik tizedesjegyet.
- **P4 (skálázás):** a négy görbe a lapszám függvényében, plusz egy **hierarchikus** stratégia (üzem → egység →
  lap → elem), ami előbb a megfelelő egységet/lapot választja ki, és csak azon belül keres. Ez a dolgozat saját
  hozzájárulása; a görbék alapján tervezzük meg, nem előre.
- **A Neo4j ezért kell:** a CypherRAG-nak adatbázis kell (ADR-0002, LPG).
- **Nem használjuk** a „leírás minden csomóponthoz GPT-vel" (szemantikus dúsítás) lépést ezrek szintjén úgy,
  ahogy a cikk tette — ezt a költséget a pilot után döntjük el (ADR-0014).

## Gyakori tévhitek

1. **„Nagyobb kontextusablakú modell megoldja."** Kitolja a falat, de nem szünteti meg: a mi generátorunk
   bármekkora üzemet előállít. És attól, hogy *befér*, még nem biztos, hogy a modell jól *használja*:
   a hosszú kontextus közepére került információt a modellek rosszabbul használják (Liu et al., „Lost in
   the Middle", arXiv 2307.03172 — nem olvastuk be `/paper-intake`-kel, a mi gráfjainkon mérni kell). A fal
   előtti romlás mérése ugyanolyan fontos, mint maga a fal.
2. **„A 0.91 azt jelenti, hogy a ContextRAG a legjobb módszer."** Egy lapon, 19 kérdésen, 2 futással. Ez a
   dolgozat egész állítása: az optimum a korpuszmérettől függ.
3. **„A CypherRAG mindig pontos, mert adatbázis-lekérdezés."** Csak ha az LLM *helyes* Cyphert ír. A cikk
   maga írja, hogy nagyobb gráfon a modell nehezen találja meg a megfelelő útvonalat.
4. **„Ha van crossover, azt biztosan megtaláljuk."** Lehet, hogy nincs: a ContextRAG a falig nyerhet, utána
   pedig egyszerűen nem futtatható. Akkor a fal *maga* a crossover, és a dolgozat nem állíthatja, hogy „a
   rangsor megfordul" — csak azt, hogy a ContextRAG elérhetetlenné válik. (Tervben: `thesis-phase-plan.md`
   P4, „Fails if".)

## Ha egyetlen dolgot olvasol el

A ChatP&ID cikk módszer- és eredményfejezete — a saját jegyzetünk róla:
`docs/private/10-literature/2603.22528.md`, az eredeti: <https://arxiv.org/abs/2603.22528>.
