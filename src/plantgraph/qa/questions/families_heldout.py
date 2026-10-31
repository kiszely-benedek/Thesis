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
    valves_on_path_candidates,
)
from plantgraph.qa.questions.families_heldout_reach import (
    downstream_isolation_candidates,
    feeding_units_candidates,
    units_reached_candidates,
)
from plantgraph.qa.questions.families_heldout_route import route_avoiding_candidates

#: The held-out families (design `heldout-families.sealed.md` part A), H1 to H6.
HELDOUT_GENERATORS: dict[QuestionFamily, CandidateGenerator] = {
    QuestionFamily.FIRST_MEETING_POINT: first_meeting_point_candidates,
    QuestionFamily.DOWNSTREAM_ISOLATION: downstream_isolation_candidates,
    QuestionFamily.VALVES_ON_PATH: valves_on_path_candidates,
    QuestionFamily.FEEDING_UNITS: feeding_units_candidates,
    QuestionFamily.UNITS_REACHED: units_reached_candidates,
    QuestionFamily.ROUTE_AVOIDING: route_avoiding_candidates,
}

#: Families left out of every v2 corpus by pre-registration (ADR-0059 point 6), with the reason.
#: FIRST_MEETING_POINT only finds pairs whose flows join directly at an item, not at a tee, so
#: on v2 it covers a partial, biased subset of the joins. Its pairwise walk also runs out of
#: memory on a 1,000-sheet v2 plant.
V2_EXCLUDED: dict[QuestionFamily, str] = {
    QuestionFamily.FIRST_MEETING_POINT: "excluded on v2 by pre-registration",
}


def heldout_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
    v2: bool = False,
) -> dict[QuestionFamily, list[Question]]:
    """Candidates of every held-out family on one corpus, by family.

    With `v2=True` the families in `V2_EXCLUDED` are not enumerated: they get an empty list
    (excluded by pre-registration; their pairwise walk also runs out of memory at 1,000 sheets).
    """
    return {
        family: (
            []
            if v2 and family in V2_EXCLUDED
            else generator(plant, manifest, sheets, corpus_id=corpus_id, seed=seed)
        )
        for family, generator in HELDOUT_GENERATORS.items()
    }
