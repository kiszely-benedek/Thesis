"""The trim machinery: plans, numbering, role decks; every trim together; determinism."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from trim_everything import ALL_ON, build_everything
from trim_harness import STYLE, TrimHarness, assert_round_trip

from plantgraph.benchmark.v2 import trims_valves
from plantgraph.benchmark.v2.class_decks import ROLE_CLASSES, role_deck_variants
from plantgraph.benchmark.v2.config import TrimConvention
from plantgraph.benchmark.v2.tags import parse_line_number, parse_tag
from plantgraph.benchmark.v2.trim_context import LineStyle, UnitNumbering
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine, main_line
from plantgraph.benchmark.v2.vocabulary import item_kind
from plantgraph.graph.schema import PIPING_CLASSES, Relation


def test_every_class_in_every_deck_is_a_piping_class() -> None:
    named = {name for classes in ROLE_CLASSES.values() for name in classes}
    assert named <= PIPING_CLASSES
    assert set(role_deck_variants()) >= {f"role:{role}" for role in ROLE_CLASSES}


def test_primary_classes_are_dealt_twice_per_deck() -> None:
    """Rule V: the primary option twice, each alternative once."""
    deck = role_deck_variants()["role:block_valve"]
    assert sorted(deck) == ["ButterflyValve", "GateValve", "GateValve"]


def test_numbering_counters_are_separate_and_tags_unique() -> None:
    numbering = UnitNumbering(3)
    assert numbering.part_tag("GateValve") == "GTV-3001"
    assert numbering.part_tag("GateValve") == "GTV-3002"
    assert numbering.part_tag("BallValve") == "BV-3001"  # own counter per valve code
    assert numbering.part_tag("PipeTee") is None
    first, second = numbering.part_tag("ConicalStrainer"), numbering.part_tag("SwingCheckValve")
    assert first == "STR-3001" and second == "CHV-3001"  # a fitting has the shared counter
    assert numbering.equipment_tag("V") == "V-301" and numbering.equipment_tag("V") == "V-302"
    assert numbering.line_number(LineStyle(size=4)) == "4-P-30001-A1A-N"


def test_a_part_class_that_is_not_a_valve_or_fitting_has_no_automatic_tag() -> None:
    with pytest.raises(ValueError, match="valve, safety device or fitting"):
        UnitNumbering(1).part_tag("FlowMeasuringElement")


def test_line_style_branch_goes_one_size_down_but_not_below_one_inch() -> None:
    assert LineStyle(size=6).branch().size == 4
    assert LineStyle(size=1).branch().size == 1
    assert LineStyle(size=6).branch(service="FL").service == "FL"


def test_a_context_for_another_unit_than_its_numbering_raises() -> None:
    h = TrimHarness()
    with pytest.raises(ValueError, match="numbering is for unit 2"):
        type(h.ctx)(
            1, h.ctx.rng, TrimConvention(), h.ctx.conventions, h.ctx.decks, UnitNumbering(2)
        )


def test_a_plan_with_an_open_run_refuses_to_be_written() -> None:
    h = TrimHarness()
    plan = trims_valves.bare_control_valve(h.ctx, STYLE, "F")
    with pytest.raises(ValueError, match="close it with with_main_line"):
        plan.write(h.builder)


def test_with_main_line_requires_the_whole_run() -> None:
    h = TrimHarness()
    plan = trims_valves.bare_control_valve(h.ctx, STYLE, "F")
    other = main_line(h.ctx, STYLE, "a", (), "b")
    with pytest.raises(ValueError, match="lacks the run parts"):
        plan.with_main_line(other)


def test_combining_plans_that_share_a_port_name_raises_until_renamed() -> None:
    h = TrimHarness()
    one = trims_valves.bare_control_valve(h.ctx, STYLE, "F")
    two = trims_valves.bare_control_valve(h.ctx, STYLE, "P")
    with pytest.raises(ValueError, match="same port"):
        combine(one, two)
    merged = combine(one.with_port_prefix("a"), two.with_port_prefix("b"))
    assert sorted(merged.ports) == ["a.body", "b.body"]
    assert len(merged.run) == 2


def test_a_tag_that_is_not_an_on_off_letter_pair_is_refused_in_limit_switches() -> None:
    h = TrimHarness()
    draft = TrimDraft(h.ctx, STYLE)
    bad = draft.tagged_part("BallValve", "valve", None)
    with pytest.raises(ValueError, match="expected a tagged on-off valve"):
        trims_valves._add_limit_switches(draft, bad)


# ---- all trims together: tags (S9), line numbers (S10), the one rule about breaks ----------------


@pytest.fixture(scope="module")
def everything() -> TrimHarness:
    h = TrimHarness(seed=5, config=TrimConvention(**ALL_ON))  # type: ignore[arg-type]
    build_everything(h)
    return h


def test_every_trim_survives_the_dexpi_round_trip_together(everything: TrimHarness) -> None:
    graph = assert_round_trip(everything)
    assert graph.number_of_nodes() > 300


def test_s9_every_tag_is_unique_parses_and_fits_its_class(everything: TrimHarness) -> None:
    """Invariant S9: unique tags; `parse_tag` reads them; the letters agree with the class."""
    tags = []
    for _, data in everything.oracle.graph.nodes(data=True):
        tag = data.get("tag")
        if tag is None:
            continue
        parsed = parse_tag(tag)
        assert parsed is not None, tag
        item_kind(data["node_class"], parsed.letters)  # raises when letters and class disagree
        tags.append(tag)
    assert len(tags) == len(set(tags))


def test_s10_every_line_number_parses_and_is_unique(everything: TrimHarness) -> None:
    """Invariant S10 (the parts a trim controls): line numbers parse and never repeat."""
    numbers = {
        d["line_number"]
        for _, _, d in everything.oracle.graph.edges(data=True)
        if d["relation"] == Relation.SEND_TO.value
    }
    assert all(parse_line_number(number) is not None for number in numbers)
    sequences = [parse_line_number(number).sequence for number in numbers]  # type: ignore[union-attr]
    assert len(sequences) == len(set(sequences))


def test_no_sensor_is_located_on_a_property_break(everything: TrimHarness) -> None:
    """pyDEXPI 1.2.0 cannot sense a break (T6): no trim may plan it."""
    graph = everything.oracle.graph
    breaks = {n for n, d in graph.nodes(data=True) if d["node_class"] == "PropertyBreak"}
    assert breaks
    assert not any(
        d["relation"] == Relation.MEASURED_BY.value and s in breaks
        for s, _, d in graph.edges(data=True)
    )


def test_every_deck_class_appears_in_the_whole_plant(everything: TrimHarness) -> None:
    present = {d["node_class"] for _, d in everything.oracle.graph.nodes(data=True)}
    wanted = {
        name for role, classes in ROLE_CLASSES.items() if role != "skillet" for name in classes
    }
    wanted |= set(ROLE_CLASSES["skillet"])
    assert wanted <= present


# ---- determinism ---------------------------------------------------------------------------------

_DIGEST_SCRIPT = """
import hashlib, json
from pydexpi.loaders.json_serializer import JsonSerializer
from plantgraph.benchmark.v2.config import TrimConvention
from trim_everything import ALL_ON, build_everything
from trim_harness import TrimHarness, project
h = TrimHarness(seed=5, config=TrimConvention(**ALL_ON))
build_everything(h)
text = json.dumps(project(h.oracle.graph), default=str).encode()
print(hashlib.sha256(text).hexdigest())
print(hashlib.sha256(JsonSerializer().export_to_bytes(h.dexpi.build())).hexdigest())
"""


def _digests(hash_seed: int) -> list[str]:
    tests_dir = Path(__file__).parent
    env = {
        **os.environ,
        "PYTHONHASHSEED": str(hash_seed),
        "PYTHONPATH": f"{tests_dir.parent}{os.pathsep}{tests_dir}",
    }
    out = subprocess.run(
        [sys.executable, "-c", _DIGEST_SCRIPT], env=env, capture_output=True, text=True, check=True
    )
    return out.stdout.split()


def test_same_seed_gives_identical_plans_under_hash_seeds_0_and_999() -> None:
    """Invariant S14 for trims: graph and DEXPI JSON bytes do not depend on `PYTHONHASHSEED`."""
    assert _digests(0) == _digests(999)


def test_same_seed_gives_the_same_plan_in_one_process_and_other_seeds_differ() -> None:
    def plan_json(seed: int) -> str:
        h = TrimHarness(seed=seed, config=TrimConvention(p_cv_station=0.5))
        plans: list[TrimPlan] = []
        for _ in range(6):
            src, dst = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
            plans.append(h.write(trims_valves.control_valve(h.ctx, STYLE, "F"), src, dst))
        return "|".join(plan.model_dump_json() for plan in plans)

    assert plan_json(1) == plan_json(1)
    assert plan_json(1) != plan_json(2)


def test_trims_leave_the_global_random_stream_alone() -> None:
    import random

    random.seed(123)
    expected = random.random()
    random.seed(123)
    h = TrimHarness()
    build_everything(h)
    assert random.random() == expected
