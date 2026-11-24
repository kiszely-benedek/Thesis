"""The user's small GLM comparison arm, stage P1g (design §20, task T13b).

The arm runs the frozen V2T-A2 system and policy (`cascade_v4_iso`) unchanged, but with a second
model, GLM 5.3 Flash on one pinned host, instead of GPT-6 Luna. It is **descriptive only**: one
sealed plant per scale, scope R questions only, no gate and no claim. What is here is pure
arithmetic and file work, so each decision the shell needs has a test:

- which two plants (the first of each scale in `plan.json` order, fixed before any plant exists);
- the question file (the A2 file with the scope X questions taken out, every other line untouched);
- the run ids, the cost estimate and the money check that comes before the first paid call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.exp0008.ledger import LedgerExhausted
from plantgraph.qa.exp0009 import caps, ledger, stages
from plantgraph.qa.exp0009.plan import SCALES, Exp0009Plan, PlantSpec22, Role
from plantgraph.qa.models import Question
from plantgraph.qa.questions.scope_x import SCOPE_X_FAMILIES

STAGE = "P1g"
MODEL_ID = "z-ai/glm-5.3-flash"
#: BAKEOFF-1/2's host. Unpinned routing spread one config over 15 hosts, so the pin names one.
PROVIDER = "fireworks"
CAP_USD = caps.STEP_CEILING_USD[STAGE]
#: the folder under the EXP-0009 root that holds the arm's question files, runs and cache
FOLDER = "p1g"
RUN_PREFIX = "G9-GLM"
_X_FAMILY_VALUES = frozenset(f.value for f in SCOPE_X_FAMILIES)


def glm_plants(plan: Exp0009Plan) -> list[PlantSpec22]:
    """The first sealed plant of each scale, in `plan.json` order (the rule PREREG A fixes).

    Raises:
        ValueError: the plan has no sealed plant at some scale.
    """
    chosen = []
    for scale in SCALES:
        sealed = plan.of_role(Role.SEALED, scale)
        if not sealed:
            raise ValueError(f"expected a sealed plant at scale {scale} in the plan, found none")
        chosen.append(sealed[0])
    return chosen


def run_id(tier: str, plant_id: str) -> str:
    """`G9-GLM-CYP-H100g22p1`: a name no Luna run can have.

    Raises:
        ValueError: the tier is not `cyp` or `ag`.
    """
    if tier not in ("cyp", "ag"):
        raise ValueError(f"expected tier 'cyp' or 'ag', found {tier!r}")
    return f"{RUN_PREFIX}-{tier.upper()}-{plant_id}"


# ---- the question file ------------------------------------------------------------------------


def scope_r_lines(a2_file_text: str) -> list[str]:
    """The lines of an A2 question file that are not scope X questions, byte for byte.

    The A2 file holds scope R plus the isolation X questions retyped as TAG_SET; X is told apart by
    its family, which the retyping leaves alone. Lines are kept as written, never re-serialized.
    """
    lines = a2_file_text.splitlines(keepends=True)
    return [
        x for x in lines if Question.model_validate_json(x).family.value not in _X_FAMILY_VALUES
    ]


def write_glm_questions(a2_dir: Path, out_dir: Path) -> int:
    """Write `out_dir/questions.jsonl` (and `splits.json` without the X ids); return the count.

    Raises:
        FileExistsError: the file is already there (a question set is never redrawn).
    """
    target = out_dir / "questions.jsonl"
    if target.exists():
        raise FileExistsError(f"expected no {target}, found one")
    text = (a2_dir / "questions.jsonl").read_text(encoding="utf-8")
    kept = scope_r_lines(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes("".join(kept).encode("utf-8"))
    kept_ids = {Question.model_validate_json(x).question_id for x in kept}
    splits = json.loads((a2_dir / "splits.json").read_text(encoding="utf-8"))
    kept_splits = {qid: split for qid, split in splits.items() if qid in kept_ids}
    document = json.dumps(kept_splits, indent=2, sort_keys=True) + "\n"
    (out_dir / "splits.json").write_bytes(document.encode("utf-8"))
    return len(kept)


# ---- money ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlantLoad:
    """One plant's share of the arm: how many questions at which scale."""

    plant_id: str
    scale: int
    n_questions: int

    @property
    def a2_rate_usd(self) -> float:
        """EXP-0008's measured sealed A2 dollars per question, both tiers, at this scale."""
        return stages.ESTIMATE_PER_QUESTION_USD[str(self.scale)]


def estimate_range_usd(loads: list[PlantLoad]) -> tuple[float, float]:
    """Low and high estimate: A2's sealed rate times GLM's dev cost ratio, over every question."""
    base = sum(load.n_questions * load.a2_rate_usd for load in loads)
    return base * caps.GLM_COST_RATIO_LOW, base * caps.GLM_COST_RATIO_HIGH


def render_estimate(root: Path, loads: list[PlantLoad], balance: str = "not read") -> str:
    """The event NOTE printed before P1g: questions, rates, estimate range, hard cap, ledgers."""
    low, high = estimate_range_usd(loads)
    rows = [f"{x.plant_id} {x.n_questions} q at ${x.a2_rate_usd} (A2 sealed rate)" for x in loads]
    ratio = f"x{caps.GLM_COST_RATIO_LOW}-{caps.GLM_COST_RATIO_HIGH} (GLM dev cost ratio)"
    return (
        f"estimate {STAGE} (GLM comparison arm, scope R only): " + "; ".join(rows)
        + f"; {ratio} = ${low:.2f}-${high:.2f}; hard cap ${CAP_USD:.2f}"
        + f"; ledger {ledger.summary(root)}; balance {balance}"
    )  # fmt: skip


def money_needed_usd(root: Path, step_dir: Path) -> float:
    """What the stage may still spend: its cap less what it spent, if the runs ledger can cover it.

    A restarted stage asks for less, because its finished runs already paid.

    Raises:
        LedgerExhausted: the cap is spent, or the runs ledger has less than the stage may spend.
    """
    needed = round(CAP_USD - ledger.runs_spent_usd(step_dir), 6)
    if needed <= 0:
        raise LedgerExhausted(f"expected money under the ${CAP_USD:.2f} cap of {STAGE}, found none")
    room = round(ledger.RUNS_CAP_USD - ledger.runs_spent_usd(root), 6)
    if room < needed:
        raise LedgerExhausted(
            f"expected ${needed:.2f} of room in the ${ledger.RUNS_CAP_USD} runs ledger for "
            f"{STAGE}, found ${room:.2f}"
        )
    return needed
