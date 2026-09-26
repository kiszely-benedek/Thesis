"""`scale_smoke`: measure a single run through the full `generate -> plant_graph -> split` path.

This is the tool for `plant-generator.md` §7 and §9 step 7. The design note gave
estimates for how long generation takes at large plant sizes (§7 "Estimates, not
measurements") — this module turns those estimates into **measurements**: it
times the same five stages with `time.perf_counter` as the prototype's table
(build, loader, conceptual, adapter, split), plus — on request — the whole run's
peak memory with `tracemalloc`. `plant-generator.md` §2's kill criterion (10
minutes, or running out of memory, on the largest planned plant) can be
decided from this.

**Why there is a `--no-memory` flag.** `tracemalloc` intercepts every single
memory allocation, so it distorts the stages that allocate the most the
worst — which is exactly the wall-clock time the kill criterion is based on.
Measured on 2026-09-20, `n_units=50, budget=4, seed=0`:

| stage      | with tracemalloc (s) | without tracemalloc (s) | distortion |
|------------|----------------------|--------------------------|------------|
| build      | 0.730                | 0.171                    | 4.3x       |
| loader     | 0.742                | 0.162                    | 4.6x       |
| conceptual | 3.424                | 0.378                    | 9.1x       |
| adapter    | 0.062                | 0.015                    | 4.1x       |
| split      | 0.285                | 0.100                    | 2.9x       |

The `conceptual` value without tracemalloc (0.378 s) matches the 2026-09-13
prototype table (0.349 s, at 50 units, §7) — the one with tracemalloc does not.
So a run meant for timing and a run meant for memory measurement must never
share one process: `--no-memory` skips `tracemalloc` entirely, and the result's
`memory_traced` field records which mode produced the number — so a value
copied into a run note can never be confused with the other kind.

Important: this tool does **not** run `rejoin`. The unmeasured hotspot noted in
§7 (`rejoin._stub_edge_attrs`, which scans the sheet list row by row) does not
run on this path — it only shows up on the rejoin path, which this smoke test
deliberately does not measure (§9 step 7's exact scope: generate ->
plant_graph -> split). This module does not fix that hotspot.

Run with: `python -m plantgraph.benchmark.scale_smoke --n-units N --budget B --seed S`.
The large, ~1000+ sheet measurement is run by the user and written up as a run
note — this module only supplies the tool, it does not replace the measurement.
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
    """All the numbers from one `scale_smoke` run: sizes, the five stages' timing, peak memory.

    `peak_memory_bytes` is only filled in if `memory_traced` is true — under
    `--no-memory` it stays `None`, never `0`, so it can't be mistaken for a real
    zero measurement (see the module docstring).
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
    """Run the `generate -> plant_graph -> split` path, timing each stage (§7).

    The five stages' order is exactly the prototype table's column order: build
    (constructing the `DexpiModel`), loader (loading the full "complete" graph
    with the linear loader), conceptual (pyDEXPI's own consolidation), adapter
    (translation to the schema's `DiGraph`), and split (the splitter's full call).

    With `trace_memory=False`, `tracemalloc` never even starts — so the timing
    isn't distorted by memory-tracking overhead (see the table in the module
    docstring).
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
    """Run `action`; return the result together with the measured time (`perf_counter`)."""
    start = time.perf_counter()
    result = action()
    return result, time.perf_counter() - start


def _print_human(result: ScaleSmokeResult) -> None:
    """A summary meant for human reading — alongside the JSON, not instead of it (see `main`)."""
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
    """CLI entry point: `python -m plantgraph.benchmark.scale_smoke ...`."""
    args = _parse_args(argv)
    result = run_scale_smoke(args.n_units, args.budget, args.seed, trace_memory=not args.no_memory)
    if not args.json:
        _print_human(result)
    # the JSON line is always printed, so it can be copied into a run note
    # without manual retyping (the user's request)
    print(json.dumps(result.model_dump()))


if __name__ == "__main__":
    main()
