"""Every question family implemented so far, collected under one name (design §9).

One place to iterate every family, for the sampler (`sample.py`), the
availability report and the tests.
"""

from __future__ import annotations

from collections.abc import Callable

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

#: Every family this task implements, keyed by its `QuestionFamily` value.
FAMILY_CANDIDATE_GENERATORS: dict[QuestionFamily, CandidateGenerator] = {
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


def all_candidates(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    *,
    corpus_id: str,
    seed: int,
) -> dict[QuestionFamily, list[Question]]:
    """Every implemented family's candidates on one corpus, keyed by family.

    Feeds the sampler and the availability report (design §9, "Sampling");
    the harness reads the sampled, seeded JSONL instead.
    """
    return {
        family: generator(plant, manifest, sheets, corpus_id=corpus_id, seed=seed)
        for family, generator in FAMILY_CANDIDATE_GENERATORS.items()
    }
