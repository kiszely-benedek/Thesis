"""Build one variant corpus: plant, split, tag variants, localization and candidate pairs.

A corpus is fully described by its `CorpusSpec`, so `decide` can rebuild exactly the corpus that
`build` described instead of storing the sheet graphs.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import get_args

from pydantic import BaseModel, ConfigDict, model_validator

from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.tag_variants import Family, VariantConfig, VariantDraw, apply_tag_variants
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2
from plantgraph.ingest.pipeline import generate_plant_graph
from plantgraph.resolution.connector_labels import read_connector_labels
from plantgraph.resolution.identity_candidates import (
    CandidateSet,
    ContentKey,
    content_key_of,
    generate_candidates,
)
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.pairing import pair_connectors

DEV_SEED = (
    1  # the only seed a threshold may be tuned on (design 5.5); every other seed is a test seed
)
ALL_FAMILIES: tuple[Family, ...] = get_args(Family)


class CorpusSpec(BaseModel):
    """Everything that determines a corpus."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    target_sheets: int
    seed: int
    duplication_rate: float
    families: tuple[Family, ...]

    @model_validator(mode="after")
    def _has_a_family(self) -> CorpusSpec:
        if not self.families:
            raise ValueError("expected at least one tag-variant family, got none")
        return self


def corpus_id_for(
    target_sheets: int, seed: int, duplication_rate: float, families: Sequence[str]
) -> str:
    """Compose the design's id (section 4): D/H + sheets + g2, `d100` at rate 1.0, `V` or `Vf`."""
    prefix = "D" if seed == DEV_SEED else "H"
    rate = {1.0: "d100", 0.25: ""}.get(duplication_rate)
    if rate is None:
        raise ValueError(
            f"expected duplication rate 1.0 or 0.25 to compose an id, got {duplication_rate}"
        )
    suffix = {("format",): "Vf", ("format", "naming"): "V"}.get(tuple(sorted(families)))
    if suffix is None:
        raise ValueError(
            f"expected families format or format+naming to compose an id, got {list(families)}"
        )
    return f"{prefix}{target_sheets}g2{rate}{suffix}"


class Corpus:
    """One localized variant corpus with its candidates, gold groups and variant draws."""

    def __init__(self, spec: CorpusSpec) -> None:
        started = time.perf_counter()
        self.spec = spec
        preset = HeadlinePresetV2(duplication_rate=spec.duplication_rate)
        search = smallest_n_units_v2(spec.target_sheets, preset, spec.seed)
        plant = generate_plant_graph(preset.generator_config(search.n_units, spec.seed))
        self.generate_s = time.perf_counter() - started
        sheets, manifest = split(plant, preset.split_config(spec.seed))
        config = VariantConfig(profile="exp0004", families=spec.families, rate=1.0, seed=spec.seed)
        varied, self.manifest, self.draws = apply_tag_variants(sheets, manifest, config)
        self.sheets, self.occurrence_map = localize(varied)
        self.n_units = search.n_units
        self.candidates = _candidates(self.sheets)
        self.gold_group_of = gold_group_index(self.manifest, self.occurrence_map, self.sheets)
        self.draw_of = draw_index(self.draws, self.occurrence_map, self.sheets)


def _candidates(sheets: list[SheetGraph]) -> CandidateSet:
    """Blocking over the localized sheets, with the resolver's own connector pairs for the card."""
    labels = [label for sheet in sheets for label in read_connector_labels(sheet)[0]]
    pairs, _ = pair_connectors(labels, {sheet.sheet_id for sheet in sheets})
    return generate_candidates(sheets, pairs)


def content_keys(sheets: Sequence[SheetGraph]) -> dict[str, ContentKey]:
    """Local key "sheet:node" to content key, for every tagged node."""
    return {
        f"{sheet.sheet_id}:{node_id}": content_key_of(sheet.sheet_id, attributes)
        for sheet in sheets
        for node_id, attributes in sheet.graph.nodes(data=True)
        if attributes.get("tag") and attributes.get("node_class")
    }


def gold_group_index(
    manifest: SplitManifest, occurrence_map: OccurrenceMap, sheets: Sequence[SheetGraph]
) -> dict[ContentKey, int]:
    """Content key to the index of its gold identity group."""
    to_local = {original: local for local, original in occurrence_map.local_to_original.items()}
    keys = content_keys(sheets)
    groups: Sequence[IdentityGroup] = manifest.identity_groups
    return {
        keys[to_local[member]]: index
        for index, group in enumerate(groups)
        for member in (group.home, *group.references)
    }


def draw_index(
    draws: Sequence[VariantDraw], occurrence_map: OccurrenceMap, sheets: Sequence[SheetGraph]
) -> dict[ContentKey, VariantDraw]:
    """Content key of each rewritten reference (as printed after the rewrite) to its draw."""
    to_local = {original: local for local, original in occurrence_map.local_to_original.items()}
    keys = content_keys(sheets)
    return {keys[to_local[draw.reference_key]]: draw for draw in draws}
