"""The six held-out families, collected under one name (EXP-0006, ADR-0035).

Kept out of `families.FAMILY_CANDIDATE_GENERATORS` on purpose: the default question set
(`python -m plantgraph.qa.questions`) must stay exactly what it was before these families
existed. Only `sealed_set.py` asks for them, explicitly.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.families import CandidateGenerator
from plantgraph.qa.questions.families_heldout_paths import (
    first_meeting_point_candidates,
    route_avoiding_candidates,
    valves_on_path_candidates,
)
from plantgraph.qa.questions.families_heldout_reach import (
    downstream_isolation_candidates,
    feeding_units_candidates,
    units_reached_candidates,
)

#: The held-out families (design `heldout-families.sealed.md` part A), H1 to H6.
HELDOUT_GENERATORS: dict[QuestionFamily, CandidateGenerator] = {
    QuestionFamily.FIRST_MEETING_POINT: first_meeting_point_candidates,
    QuestionFamily.DOWNSTREAM_ISOLATION: downstream_isolation_candidates,
    QuestionFamily.VALVES_ON_PATH: valves_on_path_candidates,
    QuestionFamily.FEEDING_UNITS: feeding_units_candidates,
    QuestionFamily.UNITS_REACHED: units_reached_candidates,
    QuestionFamily.ROUTE_AVOIDING: route_avoiding_candidates,
}


def heldout_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> dict[QuestionFamily, list[Question]]:
    """Candidates of every held-out family on one corpus, by family."""
    return {
        family: generator(plant, manifest, sheets, corpus_id=corpus_id, seed=seed)
        for family, generator in HELDOUT_GENERATORS.items()
    }
