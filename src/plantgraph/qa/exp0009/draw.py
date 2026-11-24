"""The draw of EXP-0009 (design §19.2): seeds, size targets, tagging allocation, text prior.

It runs once, before the pre-registration, and builds no plant. Everything that costs time or needs
a plant (the size search, the documents of a plan, the prior fit) enters as a function argument, so
the rules here are tested in milliseconds; `real_sizer`, `real_document_flags` and `real_prior_text`
are the production versions.

    python -m plantgraph.qa.exp0009.launcher draw --draw-seed N
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.ingest.headline_v2 import smallest_n_units_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.seed_plan import SeedPlan
from plantgraph.qa.exp0008.draw_seeds import render_markdown, write_seed_plan
from plantgraph.qa.exp0009.plan import PLANTS_PER_SCALE, Exp0009Plan, PlantSpec22, Role, plant_id

#: §17.16: the nearest total may differ from the target by this many sheets, no more
SIZE_TOLERANCE = 5
#: the size targets are drawn uniformly in these ranges (decision D5)
TARGET_RANGE = {100: (90, 110), 1000: (900, 1100)}
#: 100-sheet sealed plants that print no manual-valve tags: 4 of 5 (S9)
UNTAGGED_SEALED_100 = 4
UNTAGGED_SHARE = Fraction(4, 5)
SEEDS_FILE, PLAN_FILE, PRIOR_FILE = "seeds.json", "plan.json", "position_prior.json"

#: (target, seed) -> (n_units, predicted total sheets)
Sizer = Callable[[int, int], tuple[int, int]]
#: (n_units, seed) -> the plant's own drawn flag per document (True = manual valves untagged)
DocumentFlags = Callable[[int, int], tuple[bool, ...]]
#: () -> the text of `position_prior.json`
PriorText = Callable[[], str]

#: the order every random stream walks the plants in (design §19.2 step 2)
_DRAWN_SLOTS: tuple[tuple[Role, int, int | None], ...] = (
    (Role.VALIDATION, 100, None),
    (Role.VALIDATION, 1000, None),
    *((Role.SEALED, 100, k) for k in range(1, PLANTS_PER_SCALE + 1)),
    *((Role.SEALED, 1000, k) for k in range(1, PLANTS_PER_SCALE + 1)),
)


def round_half_up(value: Fraction) -> int:
    """The nearest integer, a half going up (S9's rounding rule), in exact arithmetic."""
    return int((value + Fraction(1, 2)) // 1)


def untagged_document_count(n_documents: int) -> int:
    """How many of a 1,000-sheet plant's documents print no manual-valve tags: round(0.8 x n)."""
    return round_half_up(UNTAGGED_SHARE * n_documents)


def draw_targets(draw_seed: int) -> dict[str, int]:
    """One size target per drawn plant, in `_DRAWN_SLOTS` order, keyed by plant id."""
    rng = random.Random(f"exp0009:targets:{draw_seed}")
    return {
        plant_id(role, scale, index): rng.randint(*TARGET_RANGE[scale])
        for role, scale, index in _DRAWN_SLOTS
    }


def require_near_target(plant: str, target: int, predicted: int) -> None:
    """Refuse a size search that landed more than `SIZE_TOLERANCE` sheets from the target.

    Raises:
        ValueError: names the plant, the target and the prediction.
    """
    if abs(predicted - target) > SIZE_TOLERANCE:
        raise ValueError(
            f"expected a total within {SIZE_TOLERANCE} sheets of the target for {plant}, "
            f"found {predicted} for target {target}"
        )


def allocate_tagging(draw_seed: int, n_documents: dict[str, int]) -> dict[str, tuple[bool, ...]]:
    """The flag per document for every drawn plant (S9 and the validation ruling).

    One stream, walked in a fixed order: VAL1000, then the five 100-sheet sealed plants (one
    `sample` picks the 4 untagged plants), then each 1,000-sheet plant's documents. VAL100 is
    untagged outright, so it consumes no draw.
    """
    rng = random.Random(f"exp0009:tagging:{draw_seed}")
    flags: dict[str, tuple[bool, ...]] = {}
    val100 = plant_id(Role.VALIDATION, 100)
    flags[val100] = (True,) * n_documents[val100]
    val1000 = plant_id(Role.VALIDATION, 1000)
    flags[val1000] = _sample_untagged(rng, n_documents[val1000])
    sealed100 = [plant_id(Role.SEALED, 100, k) for k in range(1, PLANTS_PER_SCALE + 1)]
    untagged_plants = set(rng.sample(sealed100, UNTAGGED_SEALED_100))
    for pid in sealed100:
        flags[pid] = (pid in untagged_plants,) * n_documents[pid]
    for k in range(1, PLANTS_PER_SCALE + 1):
        pid = plant_id(Role.SEALED, 1000, k)
        flags[pid] = _sample_untagged(rng, n_documents[pid])
    return flags


def _sample_untagged(rng: random.Random, n_documents: int) -> tuple[bool, ...]:
    chosen = set(rng.sample(range(n_documents), untagged_document_count(n_documents)))
    return tuple(i in chosen for i in range(n_documents))


def _seed_of(seeds: SeedPlan, role: Role, scale: int, index: int | None) -> int:
    if role is Role.VALIDATION:
        return seeds.validation[scale]
    if index is None:
        raise ValueError(f"expected a plant number for a sealed plant at {scale} sheets")
    return seeds.sealed[scale][index - 1]


def draw_plan(
    draw_seed: int,
    seeds: SeedPlan,
    sizer: Sizer,
    document_flags: DocumentFlags,
    prior_text: str,
) -> Exp0009Plan:
    """The whole plan: sizes, documents and tagging of every plant; refuses a size beyond 5 sheets.

    Raises:
        ValueError: a size search missed its target by more than `SIZE_TOLERANCE`.
    """
    targets = draw_targets(draw_seed)
    sized: dict[str, tuple[int, int, int, tuple[bool, ...]]] = {}
    for role, scale, index in _DRAWN_SLOTS:
        pid, seed = plant_id(role, scale, index), _seed_of(seeds, role, scale, index)
        sized[pid] = _size_one(pid, targets[pid], seed, sizer, document_flags)
    tagging = allocate_tagging(draw_seed, {pid: len(entry[3]) for pid, entry in sized.items()})
    drawn = [
        _spec(role, scale, index, _seed_of(seeds, role, scale, index), sized, tagging)
        for role, scale, index in _DRAWN_SLOTS
    ]
    dev = [_dev_spec(role, scale, sizer, document_flags) for role, scale in _DEV_SLOTS]
    prior = json.loads(prior_text)
    return Exp0009Plan(
        draw_seed=draw_seed,
        prior_sha256=hashlib.sha256(prior_text.encode("utf-8")).hexdigest(),
        majority_code={form: str(entry["majority"]) for form, entry in sorted(prior.items())},
        plants=tuple([*dev, *drawn]),
    )


_DEV_SLOTS = ((Role.DEV, 100), (Role.PROBE, 1000))
_DEV_SEED = 1


def _size_one(
    pid: str, target: int, seed: int, sizer: Sizer, document_flags: DocumentFlags
) -> tuple[int, int, int, tuple[bool, ...]]:
    n_units, predicted = sizer(target, seed)
    require_near_target(pid, target, predicted)
    return n_units, predicted, target, document_flags(n_units, seed)


def _spec(
    role: Role,
    scale: int,
    index: int | None,
    seed: int,
    sized: dict[str, tuple[int, int, int, tuple[bool, ...]]],
    tagging: dict[str, tuple[bool, ...]],
) -> PlantSpec22:
    pid = plant_id(role, scale, index)
    n_units, predicted, target, _own = sized[pid]
    return PlantSpec22(
        plant_id=pid,
        role=role,
        scale=scale,
        seed=seed,
        target_sheets=target,
        n_units=n_units,
        predicted_sheets=predicted,
        document_untagged=tagging[pid],
    )


def _dev_spec(role: Role, scale: int, sizer: Sizer, document_flags: DocumentFlags) -> PlantSpec22:
    """A dev plant: seed 1, target = the nominal scale, the documents' own drawn tagging."""
    pid = plant_id(role, scale)
    n_units, predicted = sizer(scale, _DEV_SEED)
    require_near_target(pid, scale, predicted)
    return PlantSpec22(
        plant_id=pid,
        role=role,
        scale=scale,
        seed=_DEV_SEED,
        target_sheets=scale,
        n_units=n_units,
        predicted_sheets=predicted,
        document_untagged=document_flags(n_units, _DEV_SEED),
    )


# ---- production versions of the three injected functions ---------------------------------------


def real_sizer(target: int, seed: int) -> tuple[int, int]:
    """The size search the ingest CLI makes: the unit count whose total is nearest the target."""
    found = smallest_n_units_v2(target, HeadlinePresetV22(), seed)
    return found.n_units, found.predicted_sheets


def real_document_flags(n_units: int, seed: int) -> tuple[bool, ...]:
    """Each document's own drawn flag, read from the plan (no pyDEXPI, seconds at 1,000 sheets)."""
    plan = plan_plant(HeadlinePresetV22().generator_config(n_units, seed))
    return tuple(document.manual_valves_untagged for document in plan.documents)


def real_prior_text() -> str:
    """Fit the POSITION text prior on dev seeds 1-5 (generates ten plants: minutes)."""
    from plantgraph.qa.exp0009 import position_baselines as pb
    from plantgraph.qa.questions.scope_x_models import NamedBy

    priors = {form: pb.fit_on_all(pb.dev_rows(form), form) for form in NamedBy}
    return pb.priors_as_json(priors)


# ---- writing and printing ---------------------------------------------------------------------


def write_draw(prereg: Path, seeds: SeedPlan, plan: Exp0009Plan, prior_text: str) -> list[Path]:
    """Write `seeds.json`, `plan.json` and `position_prior.json`; writes nothing if one exists.

    Raises:
        FileExistsError: one of the three files is already there (a draw is never redone).
    """
    paths = [prereg / SEEDS_FILE, prereg / PLAN_FILE, prereg / PRIOR_FILE]
    present = [p for p in paths if p.exists()]
    if present:
        raise FileExistsError(f"expected no draw files in {prereg}, found {present[0].name}")
    write_seed_plan(seeds, paths[0])
    with paths[1].open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(plan.model_dump_json(indent=2) + "\n")
    with paths[2].open("xb") as handle:  # bytes: the file must hash as `plan.json` says it does
        handle.write(prior_text.encode("utf-8"))
    return paths


def render_tables(seeds: SeedPlan, plan: Exp0009Plan) -> str:
    """The PREREG A tables: seeds, then per plant target, units, total, documents, allocation."""
    rows = [
        f"| {p.plant_id} | {p.role.value} | {p.seed} | {p.target_sheets} | {p.n_units} "
        f"| {p.predicted_sheets} | {p.n_documents} | {sum(p.document_untagged)} |"
        for p in plan.plants
    ]
    head = (
        "| plant | role | seed | target | n_units | predicted sheets | documents "
        "| documents untagged |\n|---|---|---|---|---|---|---|---|"
    )
    prior = f"position prior sha256: {plan.prior_sha256}; majority code: {plan.majority_code}"
    return "\n\n".join([render_markdown(seeds), "\n".join([head, *rows]), prior])
