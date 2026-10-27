"""Which runs each paid stage has, how many questions each answers, and which v1 run prices it.

The cap formula itself is in `caps.py`; this module only wires each run id to its question file and
to the v1 run whose cost per question it is scaled from (plan section 8).
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.exp0007.caps import CapEntry, CapFile, make_entry
from plantgraph.qa.exp0007.run_costs import mean_usd_per_question, read_question_costs

#: Pilot caps are fixed, not scaled: smoke + full stay within the plan's $0.10 for both tiers.
PILOT_SMOKE_CAP_USD = 0.01
PILOT_FULL_CAP_USD = 0.04
#: What the harness reserves per question in flight in the pilot (EXP-0001's values).
PILOT_RESERVE_USD = {"cyp": 0.001, "ag": 0.003}
SMOKE_QUESTIONS = 2
TIERS = ("cyp", "ag")
#: R4's ladder: v2 corpus id -> the v1 corpus whose EXP-0001 tier runs price it.
LADDER_V1 = {"H1g2": "H1", "H3g2": "H3", "H10g2": "H10", "H30g2": "H30"}
#: R5's corpora: v2 id -> the sealed v1 corpus that prices it (d0 and d50 follow H100).
SEALED_V1 = {"H100g2": "H100", "H1000g2": "H1000", "H100g2d0": "H100", "H100g2d50": "H100"}


def count_questions(questions_file: Path) -> int:
    """Number of questions (non-empty lines) in a questions file."""
    return sum(1 for line in questions_file.read_text(encoding="utf-8").splitlines() if line)


def _v1_cost(run_dir: Path) -> float:
    return mean_usd_per_question(read_question_costs(run_dir))


def _run_id(prefix: str, tier: str, corpus: str, suffix: str = "") -> str:
    return f"{prefix}-{tier.upper()}-{corpus}{suffix}"


def pilot_caps() -> CapFile:
    """The pilot's fixed caps (the correction is what the pilot measures, so nothing scales yet)."""
    sizes = (("-SMOKE", SMOKE_QUESTIONS, PILOT_SMOKE_CAP_USD), ("", 10, PILOT_FULL_CAP_USD))
    entries = [
        CapEntry(
            run_id=_run_id("P7", tier, "D100g2", suffix),
            tier=tier,
            n_questions=n,
            v1_cost_per_question_usd=0.0,
            correction=1.0,
            cost_per_question_usd=PILOT_RESERVE_USD[tier],
            cap_usd=cap,
            basis="fixed pilot cap (plan section 5)",
        )
        for tier in TIERS
        for suffix, n, cap in sizes
    ]
    return CapFile(stage="pilot", entries=entries)


def dev_caps(
    cv1_runs: Path,
    dev_questions: Path,
    corrections: dict[str, float],
    baseline_runs: dict[str, str],
) -> CapFile:
    """Caps of the dev quality check: both tiers over the whole D100g2 dev question set."""
    n = count_questions(dev_questions)
    entries = [
        make_entry(
            _run_id("Q7", tier, "D100g2"),
            tier,
            n,
            _v1_cost(cv1_runs / baseline_runs[tier]),
            corrections[tier],
        )
        for tier in TIERS
    ]
    return CapFile(stage="dev-check", entries=entries)


def _smoke_and_full(
    prefix: str, corpus: str, n_full: int, v1_run: Path, tier: str, corr: float, floor: float | None
) -> list[CapEntry]:
    v1_cost = _v1_cost(v1_run)
    smoke = make_entry(
        _run_id(prefix, tier, corpus, "-SMOKE"), tier, SMOKE_QUESTIONS, v1_cost, corr, floor
    )
    full = make_entry(_run_id(prefix, tier, corpus), tier, n_full, v1_cost, corr, floor)
    return [smoke, full]


def r4_caps(runs_root: Path, ladder_questions: Path, corrections: dict[str, float]) -> CapFile:
    """Caps of the R4 tiers; the 2-question smoke runs on the smallest size only."""
    entries: list[CapEntry] = []
    for corpus, v1_corpus in LADDER_V1.items():
        n = count_questions(ladder_questions / corpus / "questions.jsonl")
        for tier in TIERS:
            v1_run = runs_root / "exp0001" / "runs" / f"E1-{tier.upper()}-{v1_corpus}"
            run = _smoke_and_full("E7", corpus, n, v1_run, tier, corrections[tier], None)
            entries += run if corpus == "H1g2" else run[1:]
    return CapFile(stage="r4-tiers", entries=entries)


def _measured_floor(r4_runs: Path, tier: str) -> float:
    """R4's measured v2 dollars per question at H30g2: R5's caps never go below it."""
    return _v1_cost(r4_runs / _run_id("E7", tier, "H30g2"))


def r5_caps(
    runs_root: Path,
    sealed_questions: Path,
    c1_questions: Path,
    corrections: dict[str, float],
    r4_runs: Path,
) -> CapFile:
    """Caps of the R5 tiers: four corpora, the concurrency-1 control, a smoke on H100g2."""
    entries: list[CapEntry] = []
    for tier in TIERS:
        floor = _measured_floor(r4_runs, tier)
        for corpus, v1_corpus in SEALED_V1.items():
            n = count_questions(sealed_questions / corpus / "questions.jsonl")
            v1_run = runs_root / "sealed" / "runs" / f"ST-{tier.upper()}-{v1_corpus}"
            run = _smoke_and_full("S7", corpus, n, v1_run, tier, corrections[tier], floor)
            entries += run if corpus == "H100g2" else run[1:]
    ag_v1 = runs_root / "sealed" / "runs" / "ST-AG-H1000-C1"
    n_c1 = count_questions(c1_questions / "H1000g2" / "questions.jsonl")
    entries.append(
        make_entry(
            "S7-AG-H1000g2-C1",
            "ag",
            n_c1,
            _v1_cost(ag_v1),
            corrections["ag"],
            _measured_floor(r4_runs, "ag"),
        )
    )
    return CapFile(stage="r5-tiers", entries=entries)
