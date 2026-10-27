"""Turn the `synthetic` subcommand's flags into generator and splitter configs.

Three ways in: the plain flags, `--headline` (the v1 preset, ADR-0025) and `--headline-v2` (the
v2 preset, `headline_v2.py`). The last two may size the plant with `--target-sheets`. This module
reads an argparse `Namespace` but never parses argv, prints to stdout or exits the process.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from plantgraph.benchmark.generator_dispatch import AnyGeneratorConfig
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.ingest.headline import HeadlinePreset, SizeSearchResult, smallest_n_units
from plantgraph.ingest.headline_v2 import (
    HeadlinePresetV2,
    headline_corpus_id_v2,
    smallest_n_units_v2,
)


@dataclass(frozen=True)
class SyntheticSetup:
    """The generator and splitter settings a `synthetic` run resolved from its flags."""

    n_units: int
    generator_config: AnyGeneratorConfig
    split_config: SplitConfig
    search: SizeSearchResult | None
    #: the corpus id used when `--corpus-id` is not given
    default_corpus_id: str


def synthetic_setup(args: argparse.Namespace) -> SyntheticSetup:
    """Turn the flags into configs: a headline preset, a size search, or the plain flags."""
    _check_size_flags(args)
    if args.headline_v2:
        return _headline_v2_setup(args)
    if args.headline:
        return _headline_setup(args)
    generator_config = GeneratorConfig(
        n_units=args.n_units,
        seed=args.seed,
        **_equipment_range_overrides(args),
    )
    split_config = _split_config_from_flags(args)
    return SyntheticSetup(
        args.n_units,
        generator_config,
        split_config,
        None,
        _default_corpus_id(args.n_units, split_config.sheet_equipment_budget, args.seed),
    )


def _headline_setup(args: argparse.Namespace) -> SyntheticSetup:
    preset = HeadlinePreset()
    search = (
        _search_size(args.target_sheets, smallest_n_units, preset, args.seed)
        if args.target_sheets
        else None
    )
    n_units = search.n_units if search else args.n_units
    return SyntheticSetup(
        n_units,
        preset.generator_config(n_units, args.seed),
        preset.split_config(args.seed),
        search,
        _default_corpus_id(n_units, preset.sheet_equipment_budget, args.seed),
    )


def _headline_v2_setup(args: argparse.Namespace) -> SyntheticSetup:
    preset = HeadlinePresetV2(duplication_rate=args.headline_duplication_rate)
    if args.target_sheets is None:
        return SyntheticSetup(
            args.n_units,
            preset.generator_config(args.n_units, args.seed),
            preset.split_config(args.seed),
            None,
            f"syn2-u{args.n_units}-s{args.seed}",
        )
    search = _search_size(args.target_sheets, smallest_n_units_v2, preset, args.seed)
    return SyntheticSetup(
        search.n_units,
        preset.generator_config(search.n_units, args.seed),
        preset.split_config(args.seed),
        search,
        headline_corpus_id_v2(args.target_sheets, args.seed, preset.duplication_rate),
    )


def _check_size_flags(args: argparse.Namespace) -> None:
    """Exactly one of --n-units/--target-sheets; the search and the eq range follow the preset."""
    if args.headline and args.headline_v2:
        raise SystemExit("error: --headline and --headline-v2 are two different presets; give one")
    has_preset = args.headline or args.headline_v2
    if (args.n_units is None) == (args.target_sheets is None):
        raise SystemExit("error: give exactly one of --n-units and --target-sheets")
    if args.target_sheets is not None and not has_preset:
        raise SystemExit(
            "error: --target-sheets needs --headline or --headline-v2 (the search assumes a preset)"
        )
    if has_preset and (args.eq_min is not None or args.eq_max is not None):
        raise SystemExit("error: --eq-min/--eq-max do not combine with a headline preset")


def _search_size[P](
    target_sheets: int, search: Callable[[int, P, int], SizeSearchResult], preset: P, seed: int
) -> SizeSearchResult:
    """Run the size search and report it on stderr, so stdout stays one JSON line."""
    start = time.perf_counter()
    result = search(target_sheets, preset, seed)
    print(
        f"size search: target {target_sheets} sheets -> {result.n_units} units "
        f"({result.predicted_sheets} predicted) in {time.perf_counter() - start:.2f} s",
        file=sys.stderr,
    )
    return result


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


def _default_corpus_id(n_units: int, budget: int, seed: int) -> str:
    return f"syn-u{n_units}-b{budget}-s{seed}"
