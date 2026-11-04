"""Blocking, content keys and the pair card on a hand-built three-sheet toy (X-T2).

The toy (all tags are equipment):
- sheet S1: home pump `P-1203A` (unit 12) -> home tank `TK-1201` (line 6-P-1);
- sheet S2: reference `P1203A` (the same pump, written differently) and home pump `P-1203B`
  (the installed spare: same blocking key, a different item);
- sheet S3: reference `TK 1201` (the S1 tank) and reference `P-1203B` (exact copy of S2's spare).
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.models import ConnectorPair, MatchRule
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.eval.blocking_metrics import BlockingMetrics, score_blocking
from plantgraph.resolution.identity_candidates import (
    CandidateSet,
    ContentKey,
    blocking_key,
    generate_candidates,
)

PUMP = "CentrifugalPump"
TANK = "Tank"


def _sheet(
    sheet_id: str, nodes: dict[str, dict[str, object]], edges: list[tuple[str, str]]
) -> SheetGraph:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node_id, attributes in nodes.items():
        graph.add_node(node_id, **attributes)
    for source, target in edges:
        graph.add_edge(source, target, relation="send_to", line_number="6-P-1")
    return SheetGraph(sheet_id, graph)


def toy_sheets(reverse: bool = False) -> list[SheetGraph]:
    s1 = _sheet(
        "S1",
        {
            "x1": {"node_class": PUMP, "tag": "P-1203A", "unit_id": "12"},
            "x2": {"node_class": TANK, "tag": "TK-1201", "unit_id": "12"},
        },
        [("x1", "x2")],
    )
    s2 = _sheet(
        "S2",
        {
            "y1": {"node_class": PUMP, "tag": "P1203A"},
            "y2": {"node_class": PUMP, "tag": "P-1203B", "unit_id": "12"},
        },
        [],
    )
    s3 = _sheet(
        "S3",
        {
            "z1": {"node_class": TANK, "tag": "TK 1201"},
            "z2": {"node_class": PUMP, "tag": "P-1203B"},
        },
        [],
    )
    return [s3, s2, s1] if reverse else [s1, s2, s3]


def connector_pair(from_sheet: str, to_sheet: str) -> ConnectorPair:
    return ConnectorPair(
        from_key=f"{from_sheet}:aaaa", to_key=f"{to_sheet}:bbbb", match_rule=MatchRule.LINE_NUMBER
    )


def key(sheet_id: str, tag: str, node_class: str) -> ContentKey:
    return ContentKey(sheet_id, tag, node_class)


def pair_set(candidates: CandidateSet) -> set[frozenset[ContentKey]]:
    return {pair.unordered() for pair in candidates.pairs}


# --- blocking key ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("P-1203A", "123"),
        ("P1203A", "123"),
        ("12-P-03A", "123"),
        ("U12-P-03A", "123"),
        ("p-1203a", "123"),
    ],
)
def test_formatting_variants_share_the_blocking_key(tag: str, expected: str) -> None:
    assert blocking_key(tag, PUMP) == (PUMP, expected)


def test_class_is_part_of_the_key_and_digitless_tags_have_none() -> None:
    assert blocking_key("P-1203A", PUMP) != blocking_key("P-1203A", TANK)
    assert blocking_key("P-000", PUMP) is None


# --- candidates --------------------------------------------------------------------------------


def test_toy_candidate_count_and_pairs() -> None:
    candidates = generate_candidates(toy_sheets(), [])
    expected = {
        frozenset({key("S1", "P-1203A", PUMP), key("S2", "P1203A", PUMP)}),
        frozenset({key("S1", "P-1203A", PUMP), key("S2", "P-1203B", PUMP)}),
        frozenset({key("S1", "P-1203A", PUMP), key("S3", "P-1203B", PUMP)}),
        frozenset({key("S2", "P1203A", PUMP), key("S3", "P-1203B", PUMP)}),
        frozenset({key("S1", "TK-1201", TANK), key("S3", "TK 1201", TANK)}),
    }
    assert pair_set(candidates) == expected
    assert len(candidates.pairs) == 5
    assert (candidates.n_occurrences, candidates.n_ambiguous_occurrences) == (6, 0)


def test_same_sheet_pair_is_excluded() -> None:
    # `P1203A` and `P-1203B` share a block but sit on S2 together
    same_sheet = frozenset({key("S2", "P1203A", PUMP), key("S2", "P-1203B", PUMP)})
    assert same_sheet not in pair_set(generate_candidates(toy_sheets(), []))


def test_exact_grouped_pair_is_excluded() -> None:
    # S2 and S3 both print `P-1203B`: the exact-tag resolver merges them already
    exact = frozenset({key("S2", "P-1203B", PUMP), key("S3", "P-1203B", PUMP)})
    assert exact not in pair_set(generate_candidates(toy_sheets(), []))


def test_order_is_deterministic_and_independent_of_sheet_order() -> None:
    forward = generate_candidates(toy_sheets(), [])
    backward = generate_candidates(toy_sheets(reverse=True), [])
    assert forward.model_dump_json() == backward.model_dump_json()
    ordered = [(pair.blocking_key, pair.first, pair.second) for pair in forward.pairs]
    assert ordered == sorted(ordered)


def test_a_content_key_repeated_on_one_sheet_is_left_out_and_counted() -> None:
    sheets = toy_sheets()
    sheets[0].graph.add_node("x9", node_class=PUMP, tag="P-1203A", unit_id="12")
    candidates = generate_candidates(sheets, [])
    assert candidates.n_ambiguous_occurrences == 2
    assert all(
        pair.first.tag != "P-1203A" or pair.first.sheet_id != "S1" for pair in candidates.pairs
    )


# --- the card ----------------------------------------------------------------------------------


def test_card_text_for_a_pair_with_context() -> None:
    candidates = generate_candidates(toy_sheets(), [connector_pair("S1", "S2")] * 3)
    pair = next(p for p in candidates.pairs if p.second == key("S2", "P1203A", PUMP))
    assert pair.card == "\n".join(
        [
            'Occurrence A: tag "P-1203A"; class CentrifugalPump; sheet S1; unit 12; '
            "drawn next to: TK-1201 (sends to, line 6-P-1)",
            'Occurrence B: tag "P1203A"; class CentrifugalPump; sheet S2; '
            "unit not printed; units on sheet S2: 12; drawn next to: nothing",
            "Sheets S1 and S2 are joined by 3 off-page connector pairs.",
        ]
    )


def test_card_says_when_no_connector_pair_joins_the_sheets() -> None:
    pair = generate_candidates(toy_sheets(), []).pairs[0]
    assert "No off-page connector pair joins sheets" in pair.card


def test_the_richer_occurrence_is_a_and_the_card_is_the_same_whatever_the_input_order() -> None:
    for pair in generate_candidates(toy_sheets(), []).pairs:
        a_line = pair.card.splitlines()[0]
        assert f'tag "{pair.first.tag}"' in a_line


def test_card_has_no_id_and_no_manifest_field() -> None:
    sheets = toy_sheets()
    candidates = generate_candidates(sheets, [connector_pair("S1", "S2")])
    node_ids = {node for sheet in sheets for node in sheet.graph.nodes}
    # field names of the manifest / variant draw / occurrence map; none may leak into the text
    forbidden_fields = [
        "node_id", "identity_group", "tag_variants", "reference_key", "original_tag",
        "variant_tag", "home", "references", "manifest", "operator", "family", "local_key",
    ]  # fmt: skip
    for pair in candidates.pairs:
        words = set(pair.card.replace('"', " ").replace(";", " ").replace(",", " ").split())
        assert not words & node_ids, words & node_ids
        leaked = [name for name in forbidden_fields if name in pair.card.lower()]
        assert not leaked, (leaked, pair.card)


# --- the metrics (they live in eval/, they need the gold links) --------------------------------


def gold_links() -> set[frozenset[ContentKey]]:
    return {
        frozenset({key("S1", "P-1203A", PUMP), key("S2", "P1203A", PUMP)}),
        frozenset({key("S1", "TK-1201", TANK), key("S3", "TK 1201", TANK)}),
    }


def test_toy_completeness_is_one_and_reduction_ratio_matches_hand_count() -> None:
    metrics = score_blocking(generate_candidates(toy_sheets(), []), gold_links())
    # 6 occurrences -> 15 all-pairs; 5 candidates -> 1 - 5/15
    assert metrics.model_copy(update={"reduction_ratio": None}) == BlockingMetrics(
        n_candidates=5,
        n_all_pairs=15,
        n_gold_links=2,
        n_gold_links_found=2,
        pair_completeness=1.0,
        reduction_ratio=None,
    )
    assert metrics.reduction_ratio == pytest.approx(2 / 3)


def test_a_missed_gold_link_lowers_completeness() -> None:
    missed = gold_links() | {frozenset({key("S1", "P-1203A", PUMP), key("S3", "XX-9", PUMP)})}
    metrics = score_blocking(generate_candidates(toy_sheets(), []), missed)
    assert metrics.n_gold_links_found == 2
    assert metrics.pair_completeness == pytest.approx(2 / 3)


def test_no_gold_links_gives_no_completeness() -> None:
    metrics = score_blocking(generate_candidates(toy_sheets(), []), set())
    assert metrics.pair_completeness is None
