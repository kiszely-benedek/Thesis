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
from pathlib import Path
from typing import get_args

from plantgraph.adapters.pydexpi_proteus_import import VocabularyName
from plantgraph.benchmark.split_models import ConnectorLabelDetail
from plantgraph.ingest.headline import SizeSearchResult, check_realized_sheets
from plantgraph.ingest.load_step import StoreMeasurement
from plantgraph.ingest.models import IngestResult
from plantgraph.ingest.pipeline import run_proteus, run_synthetic
from plantgraph.ingest.synthetic_setup import synthetic_setup
from plantgraph.store.neo4j_loader import DatabaseRecreationRefused
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env, missing_required_vars
from plantgraph.store.plant_rows import StoreProfile

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
    try:
        if args.command == "synthetic":
            result, search = _run_synthetic(args, settings)
        else:
            result = _run_proteus(args, settings)
    except DatabaseRecreationRefused as error:
        raise SystemExit(f"error: {error}") from error

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


def _run_synthetic(
    args: argparse.Namespace, settings: Neo4jSettings | None
) -> tuple[IngestResult, SizeSearchResult | None]:
    setup = synthetic_setup(args)
    corpus_id = args.corpus_id or setup.default_corpus_id
    result = run_synthetic(
        corpus_id=corpus_id,
        generator_config=setup.generator_config,
        split_config=setup.split_config,
        check=args.check,
        settings=settings,
        store_profile=args.store_profile,
        measurement=_measurement_from_flags(args),
    )
    return result, setup.search


def _run_proteus(args: argparse.Namespace, settings: Neo4jSettings | None) -> IngestResult:
    corpus_id = args.corpus_id or _sanitize_corpus_id(args.path.stem)
    return run_proteus(
        corpus_id=corpus_id,
        path=args.path,
        settings=settings,
        store_profile=args.store_profile,
        measurement=_measurement_from_flags(args),
        vocabulary=args.vocabulary,
    )


def _measurement_from_flags(args: argparse.Namespace) -> StoreMeasurement:
    """`--fresh-database` and `--neo4j-home`; both need a Neo4j load to act on."""
    wanted = args.fresh_database or args.neo4j_home is not None
    if wanted and args.no_neo4j:
        raise SystemExit("error: --fresh-database/--neo4j-home need the load (drop --no-neo4j)")
    return StoreMeasurement(fresh_database=args.fresh_database, neo4j_home=args.neo4j_home)


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


def _sanitize_corpus_id(text: str) -> str:
    """Replace anything the corpus_id shape check would reject with `-` (design §8)."""
    return _CORPUS_ID_UNSAFE_CHARS.sub("-", text)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_synthetic_subparser(subparsers)
    _add_proteus_subparser(subparsers)
    return parser.parse_args(argv)


def _add_measurement_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fresh-database",
        action="store_true",
        help=(
            "recreate the Neo4j database before loading (CREATE OR REPLACE DATABASE), so the "
            "store size has no leftovers; stops with the fallback if the server refuses"
        ),
    )
    parser.add_argument(
        "--neo4j-home",
        type=Path,
        default=None,
        help=(
            "the Neo4j server's home directory: after loading, checkpoint and record the store "
            "size on disk (transaction logs apart) in the result"
        ),
    )


def _add_store_profile_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store-profile",
        choices=list(get_args(StoreProfile)),
        default="both",
        help=(
            "which graph layers to store (ADR-0036): 'occurrence' = every drawn symbol, "
            "'plant' = one node per physical item, 'both' = both, linked by drawn_as"
        ),
    )


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
        "(needs --headline or --headline-v2)",
    )
    parser.add_argument(
        "--headline",
        action="store_true",
        help="apply the headline preset (ADR-0025/0028): by_unit, budget 18, drawing_only labels, "
        "duplication 0.25, exact tags, 18-36 equipment per unit; it overrides the split flags",
    )
    parser.add_argument(
        "--headline-v2",
        action="store_true",
        help="the headline preset for the v2 generator (ADR-0057): the generator's own sheets, "
        "drawing_only labels, exact tags; corpus id D<sheets>g2 (seed 1) or H<sheets>g2",
    )
    parser.add_argument(
        "--headline-duplication-rate",
        type=float,
        default=0.25,
        help="--headline-v2 only: share of cross-sheet equipment also drawn as a reference "
        "(ADR-0028 headline 0.25; the sensitivity runs use 0 and 0.5)",
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
    _add_store_profile_argument(parser)
    _add_measurement_arguments(parser)
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
    parser.add_argument(
        "--vocabulary",
        choices=list(get_args(VocabularyName)),
        default="v1",
        help=(
            "which pyDEXPI classes keep their own name (ADR-0058): 'v1' = the original 16, "
            "'v2' = the grown allowlist; use a separate --corpus-id for v2 (e.g. EX01v2)"
        ),
    )
    parser.add_argument("--no-neo4j", action="store_true", help="skip the Neo4j load entirely")
    _add_store_profile_argument(parser)
    _add_measurement_arguments(parser)
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
