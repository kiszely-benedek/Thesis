"""Per-family availability of scope R questions on one v2.2 plant (design 17.15 S6).

For every question family: how many candidates its builder makes, how many the untagged refusal
drops, and how many are kept. A family that keeps fewer than `MIN_KEPT` candidates on a forced-
untagged 100-sheet plant is pre-registered unavailable in scope R.

    uv run python -m plantgraph.qa.exp0009.availability_table --seed 1 --sheets 100 \
        --tagging untagged --out table.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.exp0009.dev_plants import dev_corpus
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.questions.families_heldout import heldout_candidates
from plantgraph.qa.questions.untagged import RefusedShare, refuse_untagged

#: a family with fewer kept candidates than this on a forced-untagged 100-sheet plant is unavailable
MIN_KEPT = 10
#: the candidate-pool seed of EXP-0008's sealed recipe (`lib_plants.sh` `sealed_questions`)
POOL_SEED = 31
_TAGGING = {"untagged": True, "tagged": False, "drawn": None}


class FamilyCount(BaseModel):
    """One family's candidates on one plant, before and after the untagged refusal."""

    model_config = ConfigDict(frozen=True)

    family: QuestionFamily
    candidates: int
    refused: int

    @property
    def kept(self) -> int:
        """Candidates left after the refusal."""
        return self.candidates - self.refused


def family_counts(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int = POOL_SEED,
) -> list[FamilyCount]:
    """Build every family's candidates on a plant (dev and held-out), refuse, and count."""
    candidates = all_candidates(plant, manifest, sheets, corpus_id=corpus_id, seed=seed)
    candidates.update(
        heldout_candidates(plant, manifest, sheets, corpus_id=corpus_id, seed=seed, v2=True)
    )
    _kept, shares = refuse_untagged(candidates)
    return [_count(family, share) for family, share in shares.items()]


def _count(family: QuestionFamily, share: RefusedShare) -> FamilyCount:
    return FamilyCount(family=family, candidates=share.candidates, refused=share.refused)


def families_below(counts: list[FamilyCount], minimum: int = MIN_KEPT) -> list[QuestionFamily]:
    """The families that keep fewer than `minimum` candidates."""
    return [c.family for c in counts if c.kept < minimum]


def main(argv: list[str] | None = None) -> None:
    """Build one dev plant, count its families and write the counts as JSON."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.availability_table")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--sheets", required=True, type=int)
    parser.add_argument("--tagging", required=True, choices=sorted(_TAGGING))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    corpus = dev_corpus(args.sheets, args.seed, untagged=_TAGGING[args.tagging])
    corpus_id = f"D{args.sheets}g22s{args.seed}"
    counts = family_counts(corpus.plant, corpus.manifest, corpus.sheets, corpus_id=corpus_id)
    rows = [{**c.model_dump(mode="json"), "kept": c.kept} for c in counts]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(f"{corpus_id} ({args.tagging}): families below {MIN_KEPT} kept: {families_below(counts)}")


if __name__ == "__main__":
    main()
