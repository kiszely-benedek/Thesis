"""The schema's class vocabulary: the pyDEXPI allowlist, the ancestry rule and the generated table.

Covers invariant S18 of the generator-v2 vocabulary design: the checked-in table equals what the
rule derives from pyDEXPI now. The v1 classes' exact rows are pinned in `test_v1_goldens.py`.
"""

from __future__ import annotations

import collections
import inspect
import re
from importlib.metadata import version
from pathlib import Path

import pydexpi.dexpi_classes.pydantic_classes as pydexpi_classes
import pytest

from plantgraph.adapters import pydexpi_vocabulary
from plantgraph.adapters.pydexpi_vocabulary import ALLOWLIST, derive_vocabulary
from plantgraph.adapters.vocabulary_table_writer import render_vocabulary_module
from plantgraph.adapters.vocabulary_tag_prefixes import TAG_PREFIXES
from plantgraph.graph import schema
from plantgraph.graph.schema_classes import NodeCategory, NodeClass
from plantgraph.graph.schema_vocabulary import VOCABULARY

GRAPH_DIR = Path(schema.__file__).parent
TABLE_PATH = GRAPH_DIR / "schema_vocabulary.py"
_STRUCTURE = {"ProcessPlant", "PlantSection", "DrawingSet", "Sheet"}
_LABEL_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")  # the Neo4j label shape the store accepts


def _by_name() -> dict[str, schema.ClassSpec]:
    return {row.name: row for row in VOCABULARY}


# ---- S18: the table is the rule's output -------------------------------------------------------


def test_the_checked_in_table_equals_the_derivation() -> None:
    assert list(VOCABULARY) == derive_vocabulary()


def test_the_table_file_is_exactly_what_the_script_would_write() -> None:
    text = render_vocabulary_module(derive_vocabulary(), version("pydexpi"))
    assert TABLE_PATH.read_text(encoding="utf-8") == text


def test_pydexpi_is_pinned_to_the_version_the_table_was_derived_from() -> None:
    assert version("pydexpi") == "1.2.0"
    assert "pyDEXPI 1.2.0" in TABLE_PATH.read_text(encoding="utf-8")


def test_graph_modules_do_not_import_pydexpi_or_benchmark() -> None:
    import_line = re.compile(r"^\s*(from|import)\s+(pydexpi|plantgraph\.(benchmark|adapters))\b")
    for path in GRAPH_DIR.glob("*.py"):
        offending = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if import_line.match(line)
        ]
        assert offending == [], f"{path.name} imports {offending}"


# ---- the allowlist -----------------------------------------------------------------------------


def test_the_allowlist_has_98_distinct_classes_and_no_custom_class() -> None:
    assert len(ALLOWLIST) == 98
    assert len(set(ALLOWLIST)) == 98
    assert not [name for name in ALLOWLIST if name.startswith("Custom")]


def test_the_allowlist_holds_every_non_custom_pydexpi_piping_class() -> None:
    piping_in_pydexpi = {
        name
        for name, member in inspect.getmembers(pydexpi_classes, inspect.isclass)
        if issubclass(member, pydexpi_classes.PipingComponent)
        and member is not pydexpi_classes.PipingComponent
        and not name.startswith("Custom")
    }
    piping_rows = {row.name for row in VOCABULARY if row.category is NodeCategory.PIPING}
    assert piping_rows == piping_in_pydexpi | {"PropertyBreak"}
    assert len(piping_in_pydexpi) == 55


def test_the_table_counts_match_the_design() -> None:
    rows = _by_name().values()
    by_category = collections.Counter(row.category.value for row in rows)
    assert by_category == {"equipment": 33, "piping": 56, "instrumentation": 5, "connector": 4}
    equipment_leaves = [r for r in rows if r.category is NodeCategory.EQUIPMENT and r.leaf]
    assert len(equipment_leaves) == 25
    by_kind = collections.Counter(row.piping_kind for row in rows if row.piping_kind)
    assert by_kind == {
        "operated": 12,
        "fitting": 23,
        "primary_element": 10,
        "safety": 6,
        "check": 3,
        "junction": 1,
        "break": 1,
    }


def test_the_only_non_leaf_generator_candidates_are_check_valve_and_the_instrument_parent() -> None:
    parents = {row.name for row in VOCABULARY if not row.leaf}
    equipment_parents = {"Pump", "Compressor", "Vessel", "HeatExchanger", "Heater"}
    equipment_parents |= {"Separator", "Filter", "Mixer"}
    piping_parents = {
        "OperatedValve",
        "SafetyValveOrFitting",
        "InlinePrimaryElement",
        "PipeFitting",
    }
    assert parents == equipment_parents | piping_parents | {
        "CheckValve",
        "ProcessInstrumentationFunction",
    }


def test_every_label_has_the_neo4j_label_shape() -> None:
    for row in VOCABULARY:
        assert row.labels[0] == row.name
        assert all(_LABEL_PATTERN.match(label) for label in row.labels), row.name


def test_a_class_outside_the_allowlist_imports_by_its_ancestors_not_as_itself() -> None:
    dropped = {"Silo", "Boiler", "CentrifugalBlower", "Conveyor", "AlternatingCurrentMotor"}
    assert not dropped & set(ALLOWLIST)


def test_representative_derived_rows() -> None:
    rows = _by_name()
    assert rows["SwingCheckValve"].labels == ("SwingCheckValve", "CheckValve", "PipingComponent")
    assert rows["SwingCheckValve"].piping_kind == "check"
    assert rows["PipeTee"].piping_kind == "junction"
    assert rows["PropertyBreak"].labels == ("PropertyBreak",)
    assert rows["PropertyBreak"].piping_kind == "break"
    assert rows["ProcessControlFunction"].labels == (
        "ProcessControlFunction",
        "ProcessInstrumentationFunction",
    )
    assert rows["Furnace"].labels == ("Furnace", "Heater", "Equipment", "TaggedPlantItem")
    assert rows["AirEjector"].labels[1] == "Compressor"  # an ejector is a compressor in pyDEXPI
    assert rows["MassFlowMeasuringElement"].piping_kind == "primary_element"
    assert rows["SpringLoadedAngleGlobeSafetyValve"].piping_kind == "safety"


# ---- the rule's guard rails --------------------------------------------------------------------


def test_deriving_a_class_pydexpi_does_not_have_raises_with_its_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pydexpi_vocabulary, "ALLOWLIST", ("NoSuchClass",))
    monkeypatch.setattr(pydexpi_vocabulary, "TAG_PREFIXES", {})
    with pytest.raises(ValueError, match="NoSuchClass"):
        derive_vocabulary()


def test_deriving_a_class_with_no_schema_root_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pydexpi_vocabulary, "ALLOWLIST", ("Nozzle",))  # a part of equipment
    monkeypatch.setattr(pydexpi_vocabulary, "TAG_PREFIXES", {})
    with pytest.raises(ValueError, match="no schema root"):
        derive_vocabulary()


def test_a_tag_prefix_for_a_class_outside_the_allowlist_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(TAG_PREFIXES, "Silo", "SI")
    with pytest.raises(ValueError, match="Silo"):
        derive_vocabulary()


def test_every_tag_prefix_belongs_to_an_allowlisted_class() -> None:
    assert set(TAG_PREFIXES) <= set(ALLOWLIST)


# ---- the enum and the schema built on the table ------------------------------------------------


def test_the_enum_is_the_table_plus_structure_plus_the_fallback() -> None:
    assert len(NodeClass) == 103
    assert {member.value for member in NodeClass} == set(ALLOWLIST) | _STRUCTURE | {"GenericItem"}


def test_every_enum_member_name_is_the_upper_snake_case_of_its_value() -> None:
    for member in NodeClass:
        assert member.name == re.sub(r"(?<!^)(?=[A-Z])", "_", member.value).upper()


def test_class_specs_cover_every_node_class_with_matching_labels() -> None:
    assert set(schema.CLASS_SPECS) == set(NodeClass)
    for name, row in _by_name().items():
        assert schema.labels_for(name) == row.labels


def test_the_category_constants_partition_the_schema() -> None:
    parts = [
        schema.EQUIPMENT_CLASSES,
        schema.PIPING_CLASSES,
        schema.CONNECTOR_CLASSES,
        {
            c.value
            for c in NodeClass
            if schema.CLASS_SPECS[c].category is NodeCategory.INSTRUMENTATION
        },
        _STRUCTURE,
        {"GenericItem"},
    ]
    assert sum(len(part) for part in parts) == 103
    assert set().union(*parts) == schema.KNOWN_CLASSES


def test_the_piping_kind_constants() -> None:
    assert len(schema.VALVE_CLASSES) == 12 + 3 + 6
    assert schema.OPERATED_VALVE_CLASSES < schema.VALVE_CLASSES
    assert schema.JUNCTION_CLASSES == {"PipeTee"}
    assert schema.BREAK_CLASSES == {"PropertyBreak"}
    assert len(schema.FITTING_CLASSES) == 23
    assert len(schema.PRIMARY_ELEMENT_CLASSES) == 10
    assert schema.PIPING_CLASSES == (
        schema.VALVE_CLASSES
        | schema.FITTING_CLASSES
        | schema.JUNCTION_CLASSES
        | schema.PRIMARY_ELEMENT_CLASSES
        | schema.BREAK_CLASSES
    )
    assert not schema.VALVE_CLASSES & (schema.FITTING_CLASSES | schema.JUNCTION_CLASSES)


def test_control_valve_bodies_are_six_operated_valves() -> None:
    straight = {"GlobeValve", "BallValve", "ButterflyValve", "AngleValve"}
    assert schema.CONTROL_VALVE_BODY_CLASSES == straight | {"AngleGlobeValve", "AngleBallValve"}
    assert schema.CONTROL_VALVE_BODY_CLASSES <= schema.OPERATED_VALVE_CLASSES


def test_importable_classes_are_the_98_plus_the_fallback() -> None:
    assert schema.IMPORTABLE_CLASSES == set(ALLOWLIST) | {"GenericItem"}


def test_untagged_classes_never_have_a_tag_prefix() -> None:
    rows = _by_name()
    assert [name for name in schema.UNTAGGED_CLASSES & set(rows) if rows[name].tag_prefix] == []


# ---- relations ---------------------------------------------------------------------------------


def test_has_agitator_is_a_topology_relation_from_vessels_and_exchangers_to_the_agitator() -> None:
    assert schema.Relation.HAS_AGITATOR in schema.TOPOLOGY_RELATIONS
    sources, targets = schema.RELATION_ENDPOINTS[schema.Relation.HAS_AGITATOR]
    assert {"Vessel", "Tank", "PressureVessel", "HeatExchanger", "TubularHeatExchanger"} <= sources
    assert not {"CentrifugalPump", "ProcessColumn", "Agitator"} & sources
    assert targets == {"Agitator", "GenericItem"}


def test_control_and_signal_endpoints_admit_the_electrical_actuator_and_the_controller() -> None:
    control_from, control_to = schema.RELATION_ENDPOINTS[schema.Relation.CONTROL]
    assert "ActuatingElectricalFunction" in control_from
    assert schema.EQUIPMENT_CLASSES <= control_to
    signal_from, signal_to = schema.RELATION_ENDPOINTS[schema.Relation.SEND_SIGNAL_TO]
    assert {"ProcessControlFunction", "ProcessInstrumentationFunction"} <= signal_from & signal_to
    assert "ActuatingElectricalFunction" in signal_to


def test_send_to_and_measured_by_cover_equipment_and_all_piping() -> None:
    send_from, send_to = schema.RELATION_ENDPOINTS[schema.Relation.SEND_TO]
    measured_from, _ = schema.RELATION_ENDPOINTS[schema.Relation.MEASURED_BY]
    everything = schema.EQUIPMENT_CLASSES | schema.PIPING_CLASSES
    assert everything <= send_from & send_to
    assert everything <= measured_from


# ---- the table writer --------------------------------------------------------------------------


def test_the_writer_keeps_the_trailing_comma_of_a_one_label_chain_and_writes_none_as_none() -> None:
    text = render_vocabulary_module([_by_name()["PropertyBreak"]], "9.9.9")
    assert '_row("PropertyBreak", ("PropertyBreak",), "piping", "break", None, True),' in text
    assert "pyDEXPI 9.9.9" in text
