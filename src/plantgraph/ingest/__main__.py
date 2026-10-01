"""`python -m plantgraph.ingest` — CLI entry point (design `kg-construction.md` §8).

Two subcommands mirror the two ways a corpus enters the pipeline: `synthetic`
builds one with the generator and the splitter, `proteus` imports one real
DEXPI drawing. Both print a single `IngestResult` JSON line to stdout — this
module owns argv, environment variables, and printing; `pipeline.py` never
touches any of the three.

Exit code is non-zero if `--check` fails (gate G1, `synthetic` only) or if the
Neo4j load's own verification step fails.

`--out DIR` additionally writes that same `IngestResult` to `DIR/ingest.json`,
as UTF-8 with no BOM (design `qa-system.md` §2.1 R6, QA-T0). It is written
with `Path.write_text`, never a shell redirect: a PowerShell `>` redirect
writes UTF-16, which `qa/corpus.py` would then fail to parse back.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.ingest.headline import (
    HeadlinePreset,
    SizeSearchResult,
    check_realized_sheets,
    smallest_n_units,
)
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import run_proteus, run_synthetic
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env, missing_required_vars

#: the three variables `neo4j_settings.from_env` needs — named here too, so a
#: user who forgot `--no-neo4j` sees exactly what to set without reading that module.
_REQUIRED_NEO4J_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")

#: mirrors `neo4j_plan._CORPUS_ID_PATTERN`'s shape — used to turn free text
#: (a file stem) into a safe default corpus_id, never to validate one.
_CORPUS_ID_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.-]")

#: the file `--out DIR` writes into; `qa/corpus.py` reads the same name back.
_INGEST_RESULT_FILENAME = "ingest.json"


def main(argv: list[str] | None = None) -> None:
    """Parse argv, run the requested pipeline, print its `IngestResult`, and set the exit code."""
    args = _parse_args(argv)
    settings = None if args.no_neo4j else _settings_from_env_or_raise()

    search: SizeSearchResult | None = None
    if args.command == "synthetic":
        result, search = _run_synthetic(args, settings)
    else:
        result = _run_proteus(args, settings)

    print(result.model_dump_json())
    if args.out is not None:
        _write_result(result, args.out)
    if search is not None:
        _exit_if_search_missed(search, result)
    if result.gate_equal is False:
        sys.exit(1)


def _exit_if_search_missed(search: SizeSearchResult, result: IngestResult) -> None:
    """The search predicts, the build decides: stop with a message if they disagree."""
    try:
        check_realized_sheets(search, result.counts.n_sheets)
    except ValueError as error:
        raise SystemExit(f"error: size search disagrees with the built corpus: {error}") from error


def _write_result(result: IngestResult, out_dir: Path) -> None:
    """Write `result` as UTF-8 JSON to `out_dir/ingest.json`, creating `out_dir` if needed.

    Pydantic's `model_dump_json` always orders fields the way the model
    declares them, so the same corpus config produces byte-identical bytes
    run to run — the "deterministic, documented layout" the design asks for.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _INGEST_RESULT_FILENAME
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


@dataclass(frozen=True)
class _SyntheticSetup:
    """The generator and splitter settings a `synthetic` run resolved from its flags."""

    n_units: int
    generator_config: GeneratorConfig
    split_config: SplitConfig
    search: SizeSearchResult | None


def _run_synthetic(
    args: argparse.Namespace, settings: Neo4jSettings | None
) -> tuple[IngestResult, SizeSearchResult | None]:
    setup = _synthetic_setup(args)
    corpus_id = args.corpus_id or _default_synthetic_corpus_id(
        setup.n_units, setup.split_config.sheet_equipment_budget, args.seed
    )
    result = run_synthetic(
        corpus_id=corpus_id,
        generator_config=setup.generator_config,
        split_config=setup.split_config,
        check=args.check,
        settings=settings,
    )
    return result, setup.search


def _synthetic_setup(args: argparse.Namespace) -> _SyntheticSetup:
    """Turn the flags into configs: the headline preset, a size search, or the plain flags."""
    _check_size_flags(args)
    if not args.headline:
        generator_config = GeneratorConfig(
            n_units=args.n_units,
            seed=args.seed,
            **_equipment_range_overrides(args),
        )
        return _SyntheticSetup(args.n_units, generator_config, _split_config_from_flags(args), None)

    preset = HeadlinePreset()
    search = _search_size(args.target_sheets, preset, args.seed) if args.target_sheets else None
    n_units = search.n_units if search else args.n_units
    return _SyntheticSetup(
        n_units, preset.generator_config(n_units, args.seed), preset.split_config(args.seed), search
    )


def _check_size_flags(args: argparse.Namespace) -> None:
    """Exactly one of --n-units/--target-sheets; the search and the eq range follow the preset."""
    if (args.n_units is None) == (args.target_sheets is None):
        raise SystemExit("error: give exactly one of --n-units and --target-sheets")
    if args.target_sheets is not None and not args.headline:
        raise SystemExit("error: --target-sheets needs --headline (the search assumes the preset)")
    if args.headline and (args.eq_min is not None or args.eq_max is not None):
        raise SystemExit("error: --eq-min/--eq-max do not combine with --headline (preset values)")


def _search_size(target_sheets: int, preset: HeadlinePreset, seed: int) -> SizeSearchResult:
    """Run the size search and report it on stderr, so stdout stays one JSON line."""
    start = time.perf_counter()
    search = smallest_n_units(target_sheets, preset, seed)
    print(
        f"size search: target {target_sheets} sheets -> {search.n_units} units "
        f"({search.predicted_sheets} predicted) in {time.perf_counter() - start:.2f} s",
        file=sys.stderr,
    )
    return search


def _equipment_range_overrides(args: argparse.Namespace) -> dict[str, int]:
    """Only the bounds the user gave, so the generator's own defaults stay the fallback."""
    overrides = {
        "equipment_per_unit_min": args.eq_min,
        "equipment_per_unit_max": args.eq_max,
    }
    return {name: value for name, value in overrides.items() if value is not None}


def _split_config_from_flags(args: argparse.Namespace) -> SplitConfig:
    return SplitConfig(
        strategy=args.strategy,
        sheet_equipment_budget=args.budget,
        seed=args.seed,
        connector_label_detail=ConnectorLabelDetail(args.label_detail),
        duplication_rate=args.duplication_rate,
        exact_match_tags=not args.inexact_tags,
    )


def _run_proteus(args: argparse.Namespace, settings: Neo4jSettings | None) -> IngestResult:
    corpus_id = args.corpus_id or _sanitize_corpus_id(args.path.stem)
    return run_proteus(corpus_id=corpus_id, path=args.path, settings=settings)


def _settings_from_env_or_raise() -> Neo4jSettings:
    """Real settings, or a `SystemExit` naming exactly which variable(s) are still missing."""
    missing = missing_required_vars()
    if missing:
        raise SystemExit(
            f"error: Neo4j needs {_REQUIRED_NEO4J_VARS} set (directly, or in .env); "
            f"missing: {missing} (or pass --no-neo4j to skip the load)"
        )
    settings = from_env()
    assert settings is not None, "missing_required_vars() reported none missing"
    return settings


def _default_synthetic_corpus_id(n_units: int, budget: int, seed: int) -> str:
    return f"syn-u{n_units}-b{budget}-s{seed}"


def _sanitize_corpus_id(text: str) -> str:
    """Replace anything the corpus_id shape check would reject with `-` (design §8)."""
    return _CORPUS_ID_UNSAFE_CHARS.sub("-", text)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_synthetic_subparser(subparsers)
    _add_proteus_subparser(subparsers)
    return parser.parse_args(argv)


def _add_synthetic_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "synthetic", help="generate a synthetic plant, split it, resolve it, and load it"
    )
    parser.add_argument("--n-units", type=int, default=None, help="number of process units")
    parser.add_argument(
        "--target-sheets",
        type=int,
        default=None,
        help="instead of --n-units: the fewest units whose corpus has at least this many sheets "
        "(needs --headline)",
    )
    parser.add_argument(
        "--headline",
        action="store_true",
        help="apply the headline preset (ADR-0025/0028): by_unit, budget 18, drawing_only labels, "
        "duplication 0.25, exact tags, 18-36 equipment per unit; it overrides the split flags",
    )
    parser.add_argument(
        "--eq-min", type=int, default=None, help="equipment per unit, lower bound (not headline)"
    )
    parser.add_argument(
        "--eq-max", type=int, default=None, help="equipment per unit, upper bound (not headline)"
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=16,
        help="sheet_equipment_budget for the splitter (ADR-0017 headline default: 16)",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="shared seed for the generator and the splitter"
    )
    parser.add_argument(
        "--strategy",
        default="flow_greedy",
        help="splitter strategy (ADR-0017 headline: flow_greedy)",
    )
    parser.add_argument(
        "--label-detail",
        choices=[detail.value for detail in ConnectorLabelDetail],
        default=ConnectorLabelDetail.FULL.value,
        help=(
            "what an off-page connector stub shows: 'full' also prints its partner's label, "
            "'drawing_only' does not (ADR-0023 headline corpora: drawing_only)"
        ),
    )
    parser.add_argument(
        "--duplication-rate",
        type=float,
        default=0.0,
        help=(
            "share, in [0, 1], of equipment with cross-sheet neighbours that is also "
            "re-drawn as a reference on those neighbouring sheets (default 0.0)"
        ),
    )
    parser.add_argument(
        "--inexact-tags",
        action="store_true",
        help="re-drawn equipment carries a slightly altered tag (only matters with duplication)",
    )
    parser.add_argument("--corpus-id", default=None, help="defaults to syn-u{N}-b{B}-s{S}")
    parser.add_argument(
        "--check", action="store_true", help="run gate G1: does resolve(split(plant)) == plant?"
    )
    parser.add_argument("--no-neo4j", action="store_true", help="skip the Neo4j load entirely")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            f"directory to also write this run's {_INGEST_RESULT_FILENAME} into, e.g. "
            "data/runs/<corpus-id> (git-ignored); not written unless this is given"
        ),
    )


def _add_proteus_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("proteus", help="import one Proteus XML drawing")
    parser.add_argument("path", type=Path, help="the Proteus XML file")
    parser.add_argument("--corpus-id", default=None, help="defaults to the sanitized file stem")
    parser.add_argument("--no-neo4j", action="store_true", help="skip the Neo4j load entirely")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            f"directory to also write this run's {_INGEST_RESULT_FILENAME} into, e.g. "
            "data/runs/<corpus-id> (git-ignored); not written unless this is given"
        ),
    )


if __name__ == "__main__":
    main()
