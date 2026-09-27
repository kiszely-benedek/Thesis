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

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
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

    if args.command == "synthetic":
        result = _run_synthetic(args, settings)
    else:
        result = _run_proteus(args, settings)

    print(result.model_dump_json())
    if args.out is not None:
        _write_result(result, args.out)
    if result.gate_equal is False:
        sys.exit(1)


def _write_result(result: IngestResult, out_dir: Path) -> None:
    """Write `result` as UTF-8 JSON to `out_dir/ingest.json`, creating `out_dir` if needed.

    Pydantic's `model_dump_json` always orders fields the way the model
    declares them, so the same corpus config produces byte-identical bytes
    run to run — the "deterministic, documented layout" the design asks for.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / _INGEST_RESULT_FILENAME
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _run_synthetic(args: argparse.Namespace, settings: Neo4jSettings | None) -> IngestResult:
    corpus_id = args.corpus_id or _default_synthetic_corpus_id(args.n_units, args.budget, args.seed)
    generator_config = GeneratorConfig(n_units=args.n_units, seed=args.seed)
    split_config = SplitConfig(
        strategy=args.strategy, sheet_equipment_budget=args.budget, seed=args.seed
    )
    return run_synthetic(
        corpus_id=corpus_id,
        generator_config=generator_config,
        split_config=split_config,
        check=args.check,
        settings=settings,
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
    parser.add_argument("--n-units", type=int, required=True, help="number of process units")
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
