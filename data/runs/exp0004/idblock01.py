"""IDBLOCK-01 on the dev corpora: blocking gate I0 and the dev thresholds for D1 and D2 (EXP-0004).

Free and offline (no model, no Neo4j). Design `docs/private/40-design/exp0004-v2.md` §2, §4, §5.5, §6:

- corpus `D<n>g2d100Vf`: dev seed 1, duplication 1.0, every reference re-written by the FORMAT family only;
- blocking: pair completeness and reduction ratio (gate I0: completeness >= 0.99);
- D0, D1 and D2 scored pair-level on the candidate set after grouping (§5.3), and group-level with
  `score_identity_groups`; a candidate pair is a true link when both occurrences are in the same gold group;
- tuning (§5.5, only with --tune): tau = the observed score that maximises pair-level F1, ties to the
  higher tau; otherwise the taus are read from --taus-json and only scored (the 1,000-sheet transfer check).

    .venv/Scripts/python data/runs/exp0004/idblock01.py --target-sheets 100 --tune --out <dir>
    .venv/Scripts/python data/runs/exp0004/idblock01.py --target-sheets 1000 --taus-json <dir>/taus.json --out <dir2>
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from pathlib import Path

from plantgraph.benchmark.models import IdentityGroup
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.tag_variants import VariantConfig, VariantDraw, apply_tag_variants
from plantgraph.eval.blocking_metrics import gold_links_from_groups, score_blocking
from plantgraph.eval.resolution_scoring import score_identity_groups
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2
from plantgraph.ingest.pipeline import generate_plant_graph
from plantgraph.resolution.connector_labels import read_connector_labels
from plantgraph.resolution.identity_candidates import (
    CandidatePair,
    CandidateSet,
    ContentKey,
    content_key_of,
    generate_candidates,
)
from plantgraph.resolution.identity_deciders import (
    ExactTagDecider,
    PairDecider,
    StringSimilarityDecider,
    UnitAwareDecider,
    string_similarity,
    units_agree,
)
from plantgraph.resolution.identity_links import decide_links, group_with_links
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.pairing import pair_connectors

DEV_SEED = 1
DUPLICATION_RATE = 1.0
FAMILIES = ("format",)


class Corpus:
    """One localized variant corpus with its candidates and its gold groups."""

    def __init__(self, target_sheets: int) -> None:
        started = time.perf_counter()
        preset = HeadlinePresetV2(duplication_rate=DUPLICATION_RATE)
        search = smallest_n_units_v2(target_sheets, preset, DEV_SEED)
        plant = generate_plant_graph(preset.generator_config(search.n_units, DEV_SEED))
        self.generate_s = time.perf_counter() - started
        sheets, manifest = split(plant, preset.split_config(DEV_SEED))
        config = VariantConfig(profile="exp0004", families=FAMILIES, rate=1.0, seed=DEV_SEED)
        varied, self.manifest, self.draws = apply_tag_variants(sheets, manifest, config)
        self.sheets, self.occurrence_map = localize(varied)
        self.n_units, self.n_sheets = search.n_units, len(self.sheets)
        self.candidates = _candidates(self.sheets)
        self.gold_group_of = _gold_group_index(self.manifest.identity_groups, self.occurrence_map, self.sheets)


def _candidates(sheets: list[SheetGraph]) -> CandidateSet:
    """Blocking over the localized sheets, with the resolver's own connector pairs for the card."""
    labels = [label for sheet in sheets for label in read_connector_labels(sheet)[0]]
    pairs, _ = pair_connectors(labels, {sheet.sheet_id for sheet in sheets})
    return generate_candidates(sheets, pairs)


def _content_keys(sheets: Sequence[SheetGraph]) -> dict[str, ContentKey]:
    """Local key "sheet:node" -> content key, for every tagged node."""
    return {
        f"{sheet.sheet_id}:{node_id}": content_key_of(sheet.sheet_id, attributes)
        for sheet in sheets
        for node_id, attributes in sheet.graph.nodes(data=True)
        if attributes.get("tag") and attributes.get("node_class")
    }


def _gold_group_index(
    groups: Sequence[IdentityGroup], occurrence_map: OccurrenceMap, sheets: Sequence[SheetGraph]
) -> dict[ContentKey, int]:
    """Content key -> index of its gold identity group."""
    to_local = {original: local for local, original in occurrence_map.local_to_original.items()}
    keys = _content_keys(sheets)
    return {
        keys[to_local[member]]: index
        for index, group in enumerate(groups)
        for member in (group.home, *group.references)
    }


def _predicted_group_index(groups: Sequence[IdentityGroup], keys: dict[str, ContentKey]) -> dict[ContentKey, int]:
    """Content key -> index of its predicted group (local keys from `group_with_links`)."""
    return {keys[member]: index for index, group in enumerate(groups) for member in (group.home, *group.references)}


def _same(index: dict[ContentKey, int], pair: CandidatePair) -> bool:
    """Both occurrences of `pair` sit in one group of `index`."""
    first, second = index.get(pair.first), index.get(pair.second)
    return first is not None and first == second


def _f1(true_positives: int, false_positives: int, false_negatives: int) -> dict[str, float | int | None]:
    """Precision, recall and F1 with their counts; None where a denominator is zero."""
    predicted, actual = true_positives + false_positives, true_positives + false_negatives
    precision = true_positives / predicted if predicted else None
    recall = true_positives / actual if actual else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {"tp": true_positives, "fp": false_positives, "fn": false_negatives,
            "precision": precision, "recall": recall, "f1": f1}


def score_decider(corpus: Corpus, decider: PairDecider) -> dict[str, object]:
    """Pair-level (on the candidates, after grouping) and group-level scores of one decider."""
    grouping = group_with_links(corpus.sheets, decide_links(corpus.candidates.pairs, decider))
    predicted = _predicted_group_index(grouping.groups, _content_keys(corpus.sheets))
    outcomes = [(_same(predicted, pair), _same(corpus.gold_group_of, pair)) for pair in corpus.candidates.pairs]
    pair_level = _f1(
        sum(1 for said, true in outcomes if said and true),
        sum(1 for said, true in outcomes if said and not true),
        sum(1 for said, true in outcomes if true and not said),
    )
    return {
        "decider": decider.name,
        "pair_level": pair_level,
        "group_level": _group_level(corpus, grouping.groups),
        "n_dropped_one_to_one": grouping.n_dropped_one_to_one,
        "n_identity_conflicts": grouping.n_identity_conflicts,
    }


def _group_level(corpus: Corpus, groups: Sequence[IdentityGroup]) -> dict[str, object]:
    """`score_identity_groups` on original keys (predicted groups translated back)."""
    to_original = corpus.occurrence_map.local_to_original
    translated = [
        IdentityGroup(home=to_original[group.home], references=[to_original[r] for r in group.references],
                      **{k: v for k, v in group.model_dump().items() if k not in ("home", "references")})
        for group in groups
    ]
    return score_identity_groups(translated, corpus.manifest.identity_groups).model_dump()


def tune(corpus: Corpus, make: type[StringSimilarityDecider] | type[UnitAwareDecider]) -> tuple[float, list[dict[str, object]]]:
    """Every observed score as a threshold; the best pair-level F1 wins, ties to the higher tau."""
    grid = sorted({round(string_similarity(p.first.tag, p.second.tag), 12) for p in corpus.candidates.pairs if p.first.tag})
    trace = [{"tau": tau, **score_decider(corpus, make(tau))} for tau in grid if tau > 0]
    best = max(trace, key=lambda row: (row["pair_level"]["f1"] or 0.0, row["tau"]))  # type: ignore[index]
    return float(best["tau"]), trace  # type: ignore[arg-type]


def per_operator(corpus: Corpus, decider: PairDecider) -> dict[str, dict[str, int]]:
    """Gold candidate pairs per operator: how many the decider's grouping recovered (descriptive)."""
    grouping = group_with_links(corpus.sheets, decide_links(corpus.candidates.pairs, decider))
    predicted = _predicted_group_index(grouping.groups, _content_keys(corpus.sheets))
    variant_operator = {draw.variant_tag: draw.operator for draw in corpus.draws}
    table: dict[str, dict[str, int]] = {}
    for pair in corpus.candidates.pairs:
        if not _same(corpus.gold_group_of, pair):
            continue
        operator = variant_operator.get(pair.first.tag) or variant_operator.get(pair.second.tag) or "none"
        row = table.setdefault(operator, {"gold": 0, "recovered": 0})
        row["gold"] += 1
        row["recovered"] += int(_same(predicted, pair))
    return dict(sorted(table.items()))


def describe(corpus: Corpus) -> dict[str, object]:
    """Corpus counts, the blocking gate and the context facts behind D2."""
    gold_links = gold_links_from_groups(corpus.manifest.identity_groups, corpus.occurrence_map, corpus.sheets)
    pairs = corpus.candidates.pairs
    gold_pairs = [p for p in pairs if _same(corpus.gold_group_of, p)]
    return {
        "seed": DEV_SEED, "duplication_rate": DUPLICATION_RATE, "families": list(FAMILIES),
        "n_units": corpus.n_units, "n_sheets": corpus.n_sheets, "generate_s": round(corpus.generate_s, 1),
        "n_identity_groups": len(corpus.manifest.identity_groups), "n_variant_draws": len(corpus.draws),
        "blocking": score_blocking(corpus.candidates, gold_links).model_dump(),
        "n_candidates_true": len(gold_pairs), "n_candidates_false": len(pairs) - len(gold_pairs),
        "units_agree_true": sum(units_agree(p) for p in gold_pairs),
        "units_agree_false": sum(units_agree(p) for p in pairs if p not in gold_pairs),
        "n_ambiguous_occurrences": corpus.candidates.n_ambiguous_occurrences,
        "n_without_digits": corpus.candidates.n_without_digits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target-sheets", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tune", action="store_true")
    mode.add_argument("--taus-json", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a measurement")
    corpus = Corpus(args.target_sheets)
    result: dict[str, object] = {"corpus": f"D{args.target_sheets}g2d100Vf", **describe(corpus)}
    if args.tune:
        tau1, trace1 = tune(corpus, StringSimilarityDecider)
        tau2, trace2 = tune(corpus, UnitAwareDecider)
        result["tuning_trace"] = {"d1": trace1, "d2": trace2}
    else:
        taus = json.loads(args.taus_json.read_text(encoding="utf-8"))
        tau1, tau2 = taus["tau1"], taus["tau2"]
    deciders: list[PairDecider] = [ExactTagDecider(), StringSimilarityDecider(tau1), UnitAwareDecider(tau2)]
    result["taus"] = {"tau1": tau1, "tau2": tau2}
    result["scores"] = [score_decider(corpus, decider) for decider in deciders]
    result["per_operator"] = {decider.name: per_operator(corpus, decider) for decider in deciders}
    args.out.mkdir(parents=True)
    (args.out / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    (args.out / "taus.json").write_text(json.dumps({"tau1": tau1, "tau2": tau2}), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "tuning_trace"}, indent=1, default=str))


if __name__ == "__main__":
    main()
