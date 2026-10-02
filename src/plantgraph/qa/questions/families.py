"""Every question family implemented so far, collected under one name (design §9).

One place to iterate every family, for the sampler (`sample.py`), the
availability report and the tests.
"""

from __future__ import annotations

from collections.abc import Callable, Collection

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.families_abstain import (
    no_path_candidates,
    unanswerable_tag_candidates,
)
from plantgraph.qa.questions.families_aggregate import (
    count_in_unit_candidates,
    cross_unit_candidates,
)
from plantgraph.qa.questions.families_dev2_local import (
    instruments_of_item_candidates,
    loops_near_item_candidates,
    same_unit_candidates,
)
from plantgraph.qa.questions.families_dev2_reach import (
    connected_candidates,
    downstream_in_unit_candidates,
    upstream_sources_candidates,
)
from plantgraph.qa.questions.families_flow import (
    flow_path_candidates,
    neighbours_downstream_candidates,
)
from plantgraph.qa.questions.families_identity import sheets_of_tag_candidates
from plantgraph.qa.questions.families_isolation import upstream_isolation_candidates
from plantgraph.qa.questions.families_lookup import lookup_type_candidates, lookup_unit_candidates
from plantgraph.qa.questions.families_loop import (
    loop_actuated_valve_candidates,
    loop_measured_equipment_candidates,
)

#: A family's candidate-generating function: same signature for every family,
#: so `all_candidates` below can call them uniformly.
CandidateGenerator = Callable[..., list[Question]]

#: The 12 families built first (dev-old, design `question-aware-retrieval.md` §8.1).
DEV_OLD_GENERATORS: dict[QuestionFamily, CandidateGenerator] = {
    QuestionFamily.LOOKUP_TYPE: lookup_type_candidates,
    QuestionFamily.LOOKUP_UNIT: lookup_unit_candidates,
    QuestionFamily.NEIGHBOURS_DOWNSTREAM: neighbours_downstream_candidates,
    QuestionFamily.LOOP_ACTUATED_VALVE: loop_actuated_valve_candidates,
    QuestionFamily.LOOP_MEASURED_EQUIPMENT: loop_measured_equipment_candidates,
    QuestionFamily.FLOW_PATH: flow_path_candidates,
    QuestionFamily.UPSTREAM_ISOLATION: upstream_isolation_candidates,
    QuestionFamily.CROSS_UNIT: cross_unit_candidates,
    QuestionFamily.COUNT_IN_UNIT: count_in_unit_candidates,
    QuestionFamily.UNANSWERABLE_TAG: unanswerable_tag_candidates,
    QuestionFamily.NO_PATH: no_path_candidates,
    QuestionFamily.SHEETS_OF_TAG: sheets_of_tag_candidates,
}

#: The 6 visible families added with the plant API (dev-new, §8.2).
DEV_NEW_GENERATORS: dict[QuestionFamily, CandidateGenerator] = {
    QuestionFamily.CONNECTED: connected_candidates,
    QuestionFamily.DOWNSTREAM_IN_UNIT: downstream_in_unit_candidates,
    QuestionFamily.INSTRUMENTS_OF_ITEM: instruments_of_item_candidates,
    QuestionFamily.UPSTREAM_SOURCES: upstream_sources_candidates,
    QuestionFamily.SAME_UNIT: same_unit_candidates,
    QuestionFamily.LOOPS_NEAR_ITEM: loops_near_item_candidates,
}

#: Every family implemented, keyed by its `QuestionFamily` value.
FAMILY_CANDIDATE_GENERATORS: dict[QuestionFamily, CandidateGenerator] = {
    **DEV_OLD_GENERATORS,
    **DEV_NEW_GENERATORS,
}


def all_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
    families: Collection[QuestionFamily] | None = None,
) -> dict[QuestionFamily, list[Question]]:
    """Candidates of `families` (default: every implemented family) on one corpus, by family.

    Feeds the sampler and the availability report (design §9, "Sampling");
    the harness reads the sampled, seeded JSONL instead.
    """
    wanted = FAMILY_CANDIDATE_GENERATORS if families is None else families
    return {
        family: FAMILY_CANDIDATE_GENERATORS[family](
            plant, manifest, sheets, corpus_id=corpus_id, seed=seed
        )
        for family in FAMILY_CANDIDATE_GENERATORS
        if family in wanted
    }
