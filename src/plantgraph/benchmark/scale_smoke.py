"""`scale_smoke`: egyetlen futás mérése a teljes `generate -> plant_graph -> split` útvonalon.

Ez a `plant-generator.md` §7 és §9 step 7 eszköze. A tervezet becsléseket adott
arra, mennyi ideig tart a generálás nagy üzemméretnél (§7 "Estimates, not
measurements") — ez a modul ezeket a becsléseket **méréssé** váltja: ugyanazt
az öt szakaszt méri `time.perf_counter`-rel, mint a prototípus táblázata
(build, loader, conceptual, adapter, split), plusz — kérésre — a teljes futás
csúcsmemóriáját `tracemalloc`-kal. A `plant-generator.md` §2 kill criterionja
(10 perc vagy memóriahiány a legnagyobb tervezett üzemen) ez alapján dönthető
el.

**Miért van `--no-memory` kapcsoló.** A `tracemalloc` minden egyes memória-
foglalást lehallgat, ezért pont azokat a szakaszokat torzítja a legjobban,
amelyek a legtöbbet allokálnak — vagyis épp a kill criterion alapjául szolgáló
falióra-időt. Mérve 2026-09-20-án, `n_units=50, budget=4, seed=0`:

| szakasz    | tracemalloc-kal (s) | tracemalloc nélkül (s) | torzítás |
|------------|----------------------|-------------------------|----------|
| build      | 0.730                | 0.171                   | 4.3x     |
| loader     | 0.742                | 0.162                   | 4.6x     |
| conceptual | 3.424                | 0.378                   | 9.1x     |
| adapter    | 0.062                | 0.015                   | 4.1x     |
| split      | 0.285                | 0.100                   | 2.9x     |

A tracemalloc nélküli `conceptual` érték (0.378 s) egyezik a 2026-09-13-i
prototípus táblázatával (0.349 s, 50 egységnél, §7) — a tracemalloc-os nem.
Ezért egy időméréshez szánt futás és egy memóriaméréshez szánt futás sosem
osztozhat egy folyamaton: `--no-memory` teljesen kihagyja a `tracemalloc`-ot,
és az eredmény `memory_traced` mezője rögzíti, melyik módban készült a szám —
hogy egy futási jegyzetbe bemásolt érték sose keveredhessen össze a másikkal.

Fontos: ez az eszköz **nem** futtatja a `rejoin`-t. A §7-ben megjegyzett,
nem mért hotspot (`rejoin._stub_edge_attrs`, amely soronként végigpásztázza a
lap-listát) ezen az úton nem fut le — az csak a rejoin-ösvényen jelentkezik,
amit ez a smoke szándékosan nem méri (§9 step 7 pontos hatóköre: generate ->
plant_graph -> split). A hotspotot ez a modul nem javítja.

Futtatás: `python -m plantgraph.benchmark.scale_smoke --n-units N --budget B --seed S`.
A nagy, ~1000+ lapos mérést a felhasználó futtatja és írja meg futási
jegyzetként — ez a modul csak az eszközt adja, a mérést nem helyettesíti.
"""

from __future__ import annotations

import argparse
import json
import time
import tracemalloc
from collections.abc import Callable, Sequence

from pydantic import BaseModel

from plantgraph.adapters.pydexpi_adapter import (
    abstract_conceptual_graph,
    load_complete_graph,
    map_conceptual_graph,
)
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split


class ScaleSmokeResult(BaseModel):
    """Egy `scale_smoke` futás összes száma: méretek, öt szakasz ideje, csúcsmemória.

    `peak_memory_bytes` csak akkor van kitöltve, ha `memory_traced` igaz —
    `--no-memory` mellett `None` marad, sosem `0`, hogy ne lehessen egy valódi
    nulla mérésnek nézni (lásd a modul docstringjét).
    """

    n_units: int
    sheet_equipment_budget: int
    seed: int
    n_nodes: int
    n_edges: int
    n_sheets: int
    n_connector_pairs: int
    stage_seconds: dict[str, float]
    memory_traced: bool
    peak_memory_bytes: int | None = None


def run_scale_smoke(
    n_units: int, sheet_equipment_budget: int, seed: int, trace_memory: bool = True
) -> ScaleSmokeResult:
    """Végigfuttatja a `generate -> plant_graph -> split` útvonalat, szakaszonként mérve (§7).

    Az öt szakasz sorrendje maga a prototípus táblázatának oszlopsora: build
    (a `DexpiModel` felépítése), loader (a teljes, "complete" gráf lineáris
    betöltővel), conceptual (pyDEXPI saját összevonása), adapter (a séma
    `DiGraph`-jára fordítás) és split (a splitter teljes hívása).

    `trace_memory=False` esetén a `tracemalloc` egyáltalán el sem indul — az
    időmérés így nem torzul a memóriakövetés overheadjétől (lásd a modul
    docstringjének táblázatát).
    """
    generator_config = GeneratorConfig(seed=seed, n_units=n_units)
    split_config = SplitConfig(seed=seed, sheet_equipment_budget=sheet_equipment_budget)
    stage_seconds: dict[str, float] = {}

    if trace_memory:
        tracemalloc.start()

    generated, stage_seconds["build"] = _timed(lambda: generate_plant(generator_config))
    complete, stage_seconds["loader"] = _timed(lambda: load_complete_graph(generated.model))
    conceptual, stage_seconds["conceptual"] = _timed(lambda: abstract_conceptual_graph(complete))
    mapped, stage_seconds["adapter"] = _timed(
        lambda: map_conceptual_graph(
            conceptual, generated.record.plant_id, generated.record.stream_kind
        )
    )
    plant, _report = mapped
    split_result, stage_seconds["split"] = _timed(lambda: split(plant, split_config))
    sheets, manifest = split_result

    peak_memory_bytes: int | None = None
    if trace_memory:
        _current_bytes, peak_memory_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    return ScaleSmokeResult(
        n_units=n_units,
        sheet_equipment_budget=sheet_equipment_budget,
        seed=seed,
        n_nodes=plant.number_of_nodes(),
        n_edges=plant.number_of_edges(),
        n_sheets=len(sheets),
        n_connector_pairs=len(manifest.connector_pairs),
        stage_seconds=stage_seconds,
        memory_traced=trace_memory,
        peak_memory_bytes=peak_memory_bytes,
    )


def _timed[T](action: Callable[[], T]) -> tuple[T, float]:
    """Lefuttatja `action`-t; visszaadja az eredményt a mért idővel (`perf_counter`) együtt."""
    start = time.perf_counter()
    result = action()
    return result, time.perf_counter() - start


def _print_human(result: ScaleSmokeResult) -> None:
    """Emberi olvasásra szánt összefoglaló — a JSON mellett, nem helyette (lásd `main`)."""
    print(
        f"n_units={result.n_units} sheet_equipment_budget={result.sheet_equipment_budget} "
        f"seed={result.seed}"
    )
    print(f"DiGraph nodes/edges: {result.n_nodes} / {result.n_edges}")
    print(f"sheets: {result.n_sheets}, connector pairs: {result.n_connector_pairs}")
    print("stage seconds:")
    for stage, seconds in result.stage_seconds.items():
        print(f"  {stage:>10}: {seconds:.3f}")
    if result.memory_traced and result.peak_memory_bytes is not None:
        print(f"peak memory: {result.peak_memory_bytes / 1_048_576:.1f} MiB")
    else:
        print("peak memory: not measured (--no-memory)")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Egyszeri mérés a generate -> plant_graph -> split útvonalon "
            "(plant-generator.md §7, §9 step 7)."
        )
    )
    parser.add_argument(
        "--n-units", type=int, required=True, help="technológiai egységek (PlantSection) száma"
    )
    parser.add_argument(
        "--budget", type=int, required=True, help="sheet_equipment_budget a splitternek"
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="közös seed a generátornak és a splitternek"
    )
    parser.add_argument(
        "--json", action="store_true", help="csak a gépi olvasható JSON-t írja ki, szöveg nélkül"
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="kihagyja a tracemalloc-ot, hogy ne torzítsa az időmérést (lásd a modul docstringjét)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI belépési pont: `python -m plantgraph.benchmark.scale_smoke ...`."""
    args = _parse_args(argv)
    result = run_scale_smoke(args.n_units, args.budget, args.seed, trace_memory=not args.no_memory)
    if not args.json:
        _print_human(result)
    # a JSON-sor mindig kiíródik, hogy a futási jegyzetbe másolható legyen
    # kézi begépelés nélkül (a felhasználó kérése)
    print(json.dumps(result.model_dump()))


if __name__ == "__main__":
    main()
