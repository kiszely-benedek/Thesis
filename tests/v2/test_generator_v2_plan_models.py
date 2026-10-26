"""Tests for the v2 plan models: frozen specs, line validation, the answer key."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    GenerationRecordV2,
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    LinkSpec,
    NodeGold,
    StreamKindV2,
    TrainRecord,
    UnitRecord,
)
from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming, TrainConventions
from plantgraph.graph.schema import Relation

_VALVE = LineItemSpec(node_id="va1", node_class="GateValve", tag="GTV-1001")


def test_specs_are_frozen() -> None:
    equipment = EquipmentSpec(node_id="eq1", node_class="Tank", unit_no=1, tag="TK-101")
    line = LineSpec(
        line_number="6-P-10001-A1A-N",
        fluid_code="P",
        unit_no=1,
        src_id="eq1",
        dst_id=None,
        items=(_VALVE,),
    )
    instrument = InstrumentSpec(
        node_id="in1",
        node_class="ActuatingFunction",
        unit_no=1,
        tag=None,
        loop_tag="FIC-1014",
        measured_variable="F",
    )
    link = LinkSpec(relation=Relation.CONTROL, source_id="in1", target_id="va1")
    for spec, field in (
        (equipment, "tag"),
        (_VALVE, "tag"),
        (line, "items"),
        (instrument, "loop_tag"),
        (link, "target_id"),
        (NodeGold(role="r", drawing_group="1:G1", sheet_group="1:1"), "role"),
    ):
        with pytest.raises(ValidationError, match="frozen"):
            setattr(spec, field, "changed")


def test_line_needs_at_least_two_joined_nodes() -> None:
    with pytest.raises(ValidationError, match="at least two nodes"):
        LineSpec(
            line_number="L", fluid_code="P", unit_no=1, src_id=None, dst_id=None, items=(_VALVE,)
        )
    with pytest.raises(ValidationError, match="at least two nodes"):
        LineSpec(line_number="L", fluid_code="P", unit_no=1, src_id="eq1", dst_id=None)


def test_open_ended_lines_are_valid_with_an_item() -> None:
    open_start = LineSpec(
        line_number="L", fluid_code="CWS", unit_no=1, src_id=None, dst_id="eq1", items=(_VALVE,)
    )
    open_end = LineSpec(
        line_number="M", fluid_code="P", unit_no=1, src_id="eq1", dst_id=None, items=(_VALVE,)
    )
    assert open_start.src_id is None
    assert open_end.dst_id is None


def test_link_rejects_send_to_and_structural_relations() -> None:
    for relation in (Relation.SEND_TO, Relation.IS_LOCATED_IN):
        with pytest.raises(ValidationError, match="link relation must be one of"):
            LinkSpec(relation=relation, source_id="a", target_id="b")


def test_equipment_unit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        EquipmentSpec(node_id="eq1", node_class="Tank", unit_no=0, tag="TK-101")


def test_record_serializes_with_its_gold_parts() -> None:
    config = GeneratorConfigV2(n_units=1)
    conventions = TrainConventions(on_off_letter=OnOffLetter.Y, spare_naming=SpareNaming.SUFFIX)
    record = GenerationRecordV2(
        plant_id="plant0",
        seed=0,
        generator_config=config.model_dump_json(),
        pydexpi_version="graph-test-builder-v2",
        trains=(TrainRecord(train_no=1, conventions=conventions),),
        units=(UnitRecord(unit_no=1, train_no=1, pattern="U4", variant="plain"),),
        stream_kind={"6-P-10001-A1A-N": StreamKindV2.PROCESS},
        node_gold={"eq1": NodeGold(role="feed_tank", drawing_group="1:G1", sheet_group="1:1")},
    )
    restored = GenerationRecordV2.model_validate_json(record.model_dump_json())
    assert restored == record
    assert restored.open_stub_count == 0
