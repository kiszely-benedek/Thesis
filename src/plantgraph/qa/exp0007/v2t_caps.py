"""Caps of R4 and R5 for the tuned system V2T-A, priced from the held-back validation runs.

F1's caps were scaled from v1 runs through a pilot correction (`cap_plans.py`). V2T has been
measured on v2 plants already (the validation plants of ADR-0061), so its caps read those runs'
real dollars per question instead: `cap = ceil_0.05(1.3 x n x c)` with `c` the measured mean
(`caps.cap_usd`). Setting A is the measured system: Cypher `cypher_rag_lines` with a 30 s
query timeout, agent `graph_agent_lines`, 120 s per question.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.exp0007.cap_plans import LADDER_V1, SEALED_V1, count_questions
from plantgraph.qa.exp0007.caps import CapEntry, CapFile, cap_usd
from plantgraph.qa.exp0007.ctx_caps import ctx_small_entries
from plantgraph.qa.exp0007.run_costs import mean_usd_per_question, read_question_costs
from plantgraph.qa.exp0007.tune_plan import SMOKE_CAP_USD, SMOKE_QUESTIONS

#: The two validation plants and their sizes (`tune_plan.VALIDATION_PLANTS`).
PLANT_100 = "X100g2s212"
PLANT_1000 = "X1000g2s213"
#: The validation runs that price each arm: run-id template per arm (`{plant}` filled in).
V2T_RUN = {"cyp": "V7-CYP-A-{plant}", "ag": "V7-AG-{plant}"}
F1_RUN = {"cyp": "V7F1-CYP-{plant}", "ag": "V7F1-AG-{plant}"}
TIERS = ("cyp", "ag")
#: R5 corpora priced by the 100-sheet plant; H1000g2 (and the control) by the 1,000-sheet one.
SEALED_100 = ("H100g2", "H100g2d0", "H100g2d50")
#: The optional F1 baseline runs on these two sealed corpora only.
F1_BASELINE_CORPORA = ("H100g2", "H1000g2")
F1_PREFIX = "S7F1"


class PlantCosts(BaseModel):
    """Measured mean dollars per question of the V2T-A and F1 tiers on one validation plant."""

    model_config = ConfigDict(frozen=True)

    plant: str
    v2t: dict[str, float]
    f1: dict[str, float]

    def of(self, system: str) -> dict[str, float]:
        """Tier -> cost of `system` (`v2t` or `f1`)."""
        return self.v2t if system == "v2t" else self.f1


class ValidationCosts(BaseModel):
    """The measured costs on both validation plants."""

    model_config = ConfigDict(frozen=True)

    small: PlantCosts
    large: PlantCosts

    def worst(self, system: str, tier: str) -> float:
        """The larger of the two plants' cost for a tier (`system` is `v2t` or `f1`)."""
        return max(p.of(system)[tier] for p in (self.small, self.large))


def _plant_costs(v7_runs: Path, plant: str) -> PlantCosts:
    def mean(template: str) -> float:
        return mean_usd_per_question(read_question_costs(v7_runs / template.format(plant=plant)))

    return PlantCosts(
        plant=plant,
        v2t={t: mean(V2T_RUN[t]) for t in TIERS},
        f1={t: mean(F1_RUN[t]) for t in TIERS},
    )


def read_validation_costs(v7_runs: Path) -> ValidationCosts:
    """Mean dollars per question of every validation run that prices a cap.

    Raises:
        FileNotFoundError: a validation run directory has no `answers.jsonl`.
    """
    return ValidationCosts(
        small=_plant_costs(v7_runs, PLANT_100), large=_plant_costs(v7_runs, PLANT_1000)
    )


def _entry(run_id: str, tier: str, n: int, measured: float, floor: float | None = None) -> CapEntry:
    """One cap: `measured` dollars per question, raised to `floor` when that is larger."""
    cost = measured if floor is None else max(measured, floor)
    basis = f"1.3 x {n} x {cost:.6f} (measured {measured:.6f} on the validation plants"
    basis += ")" if cost == measured else f", raised to R4's measured {cost:.6f})"
    return CapEntry(
        run_id=run_id,
        tier=tier,
        n_questions=n,
        v1_cost_per_question_usd=measured,
        correction=1.0,
        cost_per_question_usd=cost,
        cap_usd=cap_usd(n, cost),
        basis=basis,
    )


def _smoke_entry(run_id: str, tier: str, cost: float) -> CapEntry:
    """A 2-question smoke: the fixed small cap of the tuning smokes, `cost` is only the reserve."""
    entry = _entry(run_id, tier, SMOKE_QUESTIONS, cost)
    basis = f"fixed smoke cap (2 questions, measured {cost:.6f} per question)"
    return entry.model_copy(update={"cap_usd": SMOKE_CAP_USD, "basis": basis})


def r4_v2t_caps(
    costs: ValidationCosts, ladder_questions: Path, prompt_sizes: Path, e1_runs: Path
) -> CapFile:
    """R4: both V2T tiers on H1g2..H30g2, priced at the dearer validation plant.

    The optional ContextRAG arm (`E7-CTXH-*`, `ctx_caps.py`) is always in the file, for the same
    reason as R5's F1 baseline: the file is hashed before any call.

    The ladder plants are smaller than both validation plants, so that price is an upper bound
    for them; the smoke (2 questions) runs on H1g2 only.
    """
    entries: list[CapEntry] = []
    for corpus in LADDER_V1:
        n = count_questions(ladder_questions / corpus / "questions.jsonl")
        for tier in TIERS:
            cost = costs.worst("v2t", tier)
            if corpus == "H1g2":
                entries.append(_smoke_entry(f"E7-{tier.upper()}-{corpus}-SMOKE", tier, cost))
            entries.append(_entry(f"E7-{tier.upper()}-{corpus}", tier, n, cost))
    entries += ctx_small_entries(prompt_sizes, e1_runs, ladder_questions)
    return CapFile(stage="r4-v2t", entries=entries)


def _sealed_plant(costs: ValidationCosts, corpus: str) -> PlantCosts:
    return costs.small if corpus in SEALED_100 else costs.large


def _measured_floor(r4_runs: Path | None, tier: str) -> float | None:
    """R4's measured dollars per question at H30g2: R5's caps never go below it."""
    if r4_runs is None:
        return None
    run = r4_runs / f"E7-{tier.upper()}-H30g2"
    return mean_usd_per_question(read_question_costs(run))


def r5_v2t_caps(
    costs: ValidationCosts,
    sealed_questions: Path,
    c1_questions: Path,
    r4_runs: Path | None = None,
) -> CapFile:
    """R5: V2T on the four sealed corpora, the concurrency-1 control, and the F1 baseline.

    The F1 baseline entries (`S7F1-*`) are always in the file: the file is hashed before any
    call, and whether the baseline runs is chosen later by a flag of `run_sealed.sh`.
    """
    entries: list[CapEntry] = []
    for corpus in SEALED_V1:
        n = count_questions(sealed_questions / corpus / "questions.jsonl")
        for tier in TIERS:
            measured = _sealed_plant(costs, corpus).v2t[tier]
            floor = _measured_floor(r4_runs, tier)
            if corpus == "H100g2":
                entries.append(_smoke_entry(f"S7-{tier.upper()}-{corpus}-SMOKE", tier, measured))
            entries.append(_entry(f"S7-{tier.upper()}-{corpus}", tier, n, measured, floor))
    n_c1 = count_questions(c1_questions / "H1000g2" / "questions.jsonl")
    ag_measured = costs.large.v2t["ag"]
    entries.append(
        _entry("S7-AG-H1000g2-C1", "ag", n_c1, ag_measured, _measured_floor(r4_runs, "ag"))
    )
    for corpus in F1_BASELINE_CORPORA:
        n = count_questions(sealed_questions / corpus / "questions.jsonl")
        for tier in TIERS:
            measured = _sealed_plant(costs, corpus).f1[tier]
            entries.append(_entry(f"{F1_PREFIX}-{tier.upper()}-{corpus}", tier, n, measured))
    return CapFile(stage="r5-v2t", entries=entries)


def optional_total_usd(caps: CapFile, prefix: str) -> float:
    """The sum of the optional runs' caps: `S7F1-*` (F1 baseline) or `E7-CTXH-*` (ContextRAG)."""
    return round(sum(e.cap_usd for e in caps.entries if e.run_id.startswith(prefix)), 2)


def f1_baseline_total_usd(caps: CapFile) -> float:
    """The sum of the optional F1 baseline caps (`S7F1-*`)."""
    return optional_total_usd(caps, F1_PREFIX)
