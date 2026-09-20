"""`scale_smoke` tesztje — csak apró méretben (`plant-generator.md` §9 step 7).

A valódi, >=1000 lapos mérést a felhasználó futtatja és írja meg futási
jegyzetként; ez a teszt csak azt bizonyítja, hogy az eszköz működik és a
számai önmagukban ellentmondásmentesek, nem a méretét.
"""

from __future__ import annotations

from plantgraph.benchmark.scale_smoke import run_scale_smoke

_EXPECTED_STAGES = {"build", "loader", "conceptual", "adapter", "split"}


def test_reports_all_five_stages_with_nonnegative_seconds() -> None:
    result = run_scale_smoke(n_units=2, sheet_equipment_budget=2, seed=0)

    assert set(result.stage_seconds) == _EXPECTED_STAGES
    for stage, seconds in result.stage_seconds.items():
        assert seconds >= 0.0, f"stage {stage} reported a negative time"


def test_counts_are_self_consistent() -> None:
    result = run_scale_smoke(n_units=2, sheet_equipment_budget=2, seed=0)

    assert result.n_nodes > 0
    assert result.n_edges > 0
    assert result.n_sheets >= 1
    assert result.n_connector_pairs >= 0


# ---- tracemalloc bekapcsolva/kikapcsolva (a coordinator 2026-09-20-i mérése) ------------------


def test_with_memory_tracing_reports_a_peak_figure() -> None:
    result = run_scale_smoke(n_units=2, sheet_equipment_budget=2, seed=0, trace_memory=True)

    assert result.memory_traced is True
    assert result.peak_memory_bytes is not None
    assert result.peak_memory_bytes > 0


def test_without_memory_tracing_reports_no_peak_figure() -> None:
    # tracemalloc torzítja az időmérést (a modul docstringje méri, kb. 3-9x az
    # allokáció-heavy szakaszokon) — --no-memory ezért teljesen kihagyja, és
    # a hiányzó mérést None-nal jelzi, sosem 0-val
    result = run_scale_smoke(n_units=2, sheet_equipment_budget=2, seed=0, trace_memory=False)

    assert result.memory_traced is False
    assert result.peak_memory_bytes is None


def test_same_inputs_give_the_same_counts() -> None:
    # a generátor és a splitter is determinisztikus egy seedre (invariáns 3,
    # splitter.md §4) — ha ez elbukik, valamelyik nem az
    first = run_scale_smoke(n_units=3, sheet_equipment_budget=2, seed=1)
    second = run_scale_smoke(n_units=3, sheet_equipment_budget=2, seed=1)

    assert (first.n_nodes, first.n_edges, first.n_sheets, first.n_connector_pairs) == (
        second.n_nodes,
        second.n_edges,
        second.n_sheets,
        second.n_connector_pairs,
    )
