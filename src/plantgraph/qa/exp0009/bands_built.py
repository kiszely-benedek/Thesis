"""The composition bands of the plants as they were built (B10's sealed report, finding B4).

The **composition report** says whether generated sheets look like real ones (symbols, valves and
instruments per sheet and so on); the **bands** are the ranges it is judged against. The frozen
command `benchmark.v2.composition --seeds ...` cannot report the sealed plants: it re-sizes each
plant from its nominal 100 or 1,000 sheets (the sealed plants have drawn sizes and drawn tagging)
and it looks every seed up in EXP-0008's seed plan, which refuses EXP-0009's. Here each plant is
planned from the generator config its own `ingest.json` recorded, so the report describes the
plants that exist.

    python -m plantgraph.qa.exp0009.bands_built --root ROOT --plants H100g22p1 ... --json OUT
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from plantgraph.benchmark.v2.composition import CompositionReport, build_report, render_report
from plantgraph.benchmark.v2.composition_pool import PooledReport, pool_reports, render_pooled
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.qa.exp0009.build import INGEST_FILE


def recorded_config(ingest_json: Path) -> GeneratorConfigV22:
    """The generator config a built plant recorded: its seed, size and document tagging.

    Raises:
        ValueError: the file records no generator config.
    """
    record = json.loads(ingest_json.read_text(encoding="utf-8"))
    generator = record.get("config", {}).get("generator")
    if generator is None:
        raise ValueError(f"expected config.generator in {ingest_json}, found none")
    return GeneratorConfigV22.model_validate(generator)


def built_report(corpora_root: Path, plant_id: str) -> CompositionReport:
    """The plan rows and the sheet-graph rows of one built plant, from its own recorded config."""
    config = recorded_config(corpora_root / plant_id / INGEST_FILE)
    return build_report(plan_plant(config), plant_id, HeadlinePresetV22())


def pooled_built(corpora_root: Path, plant_ids: Sequence[str]) -> PooledReport:
    """The bands judged on the mean over the built plants of one scale (ADR-0059)."""
    return pool_reports([built_report(corpora_root, plant_id) for plant_id in plant_ids])


def main(argv: Sequence[str] | None = None) -> int:
    """Print the pooled report, write it as JSON; exit 1 when a pooled band fails."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.bands_built")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--plants", nargs="+", required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args(argv)
    pooled = pooled_built(args.root / "corpora", args.plants)
    for report in pooled.plants:
        print(render_report(report))
    print(render_pooled(pooled))
    args.json.write_text(json.dumps(pooled.model_dump(mode="json"), indent=2), encoding="utf-8")
    return 1 if pooled.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
