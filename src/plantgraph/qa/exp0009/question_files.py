"""From pools to question files: the drop set, the samples, the A2 and B files (design §19.6).

Scope R is the families EXP-0008 asked; scope X is the five extension families. A2 (the frozen
system) is asked R plus the isolation X questions retyped as `TAG_SET`, the only list type it
knows; B (the revised system) is asked R plus every X question. Both files hold the same
questions, so SB1 and SB2 can pair rows by the question id with the corpus id stripped.

The drop set is fixed **after** every pool of a role exists and **before** any sampling, so the
choice of families never depends on what the samples happened to hold.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from plantgraph.qa.exp0009.gates import MIN_KEPT
from plantgraph.qa.exp0009.plan import b_id_of
from plantgraph.qa.exp0009.position_baselines import FormPrior
from plantgraph.qa.exp0009.questions import R_UNAVAILABLE, PlantPool, Recipe
from plantgraph.qa.harness.family_meta import FAMILY_META
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.per_family import sample_family, sample_per_family
from plantgraph.qa.questions.scope_x import SCOPE_X_DEV_FAMILIES, for_a2
from plantgraph.qa.questions.scope_x_models import NamedBy
from plantgraph.qa.questions.sealed_set import sample_sealed_set

QUESTIONS_FILE, SPLITS_FILE, REPORT_FILE = "questions.jsonl", "splits.json", "scope_report.json"
BASELINES_FILE = "position_baselines.jsonl"
#: the splits of the X families (`scope_x.py`: dev families are tuned on, held-out ones are sealed)
X_DEV_SPLIT, X_HELD_OUT_SPLIT = "x-dev", "x-held-out"


@dataclass(frozen=True)
class DropSet:
    """Families left out of every sample of a role, and why."""

    pre_registered: frozenset[QuestionFamily]
    #: G0e: fewer than `MIN_KEPT` kept candidates on some plant of the role
    too_few: frozenset[QuestionFamily]

    @property
    def all(self) -> frozenset[QuestionFamily]:
        """Every dropped family."""
        return self.pre_registered | self.too_few


def kept_counts(pool: PlantPool) -> Counter[QuestionFamily]:
    """Kept candidates per family on one plant: the R pool's members plus the kept X questions."""
    counts: Counter[QuestionFamily] = Counter(q.family for q in pool.r_pool)
    for family, kept in pool.x_kept.items():
        counts[family] += len(kept)
    return counts


def drop_set(pools: Mapping[str, PlantPool], x_families: Sequence[QuestionFamily]) -> DropSet:
    """The drop set of a role: the five pre-registered R families, and G0e's too-few families.

    `x_families` are the X families the role is asked, so an X family that was never built (a
    held-out one on a dev plant) is not mistaken for an empty one.
    """
    counts = [kept_counts(pool) for pool in pools.values()]
    r_families = {f for c in counts for f in c if f not in R_UNAVAILABLE and f not in x_families}
    judged = r_families | set(x_families)
    too_few = {f for f in judged if any(c[f] < MIN_KEPT for c in counts)}
    return DropSet(pre_registered=frozenset(R_UNAVAILABLE), too_few=frozenset(too_few))


# ---- samples ---------------------------------------------------------------------------------


def sample_r(
    pool: PlantPool, drop: DropSet, recipe: Recipe
) -> tuple[list[Question], dict[str, str]]:
    """Scope R: the EXP-0008 recipe over the pool without the dropped families."""
    usable = [q for q in pool.r_pool if q.family not in drop.all]
    if recipe.n_per_wording:  # sealed: also the held-out wordings of ten dev families
        sealed = sample_sealed_set(
            usable, recipe.n_per_family, recipe.n_per_wording, recipe.sample_seed, v2=True
        )
        return sealed.questions, sealed.splits
    drawn = sample_per_family(usable, recipe.n_per_family, recipe.sample_seed)
    return drawn, {q.question_id: FAMILY_META[q.family].split.value for q in drawn}


def sample_x(pool: PlantPool, drop: DropSet, recipe: Recipe) -> list[Question]:
    """Scope X: ten per family with the same sample seed as R; no stratification (R11, R13.4)."""
    return [
        q
        for family, kept in pool.x_kept.items()
        if family not in drop.all
        for q in sample_family(kept, recipe.n_per_family, recipe.sample_seed)
    ]


def x_split(question: Question) -> str:
    """`x-dev` or `x-held-out`, by family."""
    return X_DEV_SPLIT if question.family in SCOPE_X_DEV_FAMILIES else X_HELD_OUT_SPLIT


# ---- the two files ---------------------------------------------------------------------------


def relabel_question(question: Question, from_id: str, to_id: str) -> Question:
    """The question under another corpus id; only `corpus_id` and the id's prefix change.

    Raises:
        ValueError: the question id does not start with `from_id` and a colon.
    """
    prefix = f"{from_id}:"
    if question.corpus_id != from_id or not question.question_id.startswith(prefix):
        raise ValueError(
            f"expected corpus {from_id} and an id starting {prefix!r}, found {question.question_id}"
        )
    return question.model_copy(
        update={"corpus_id": to_id, "question_id": f"{to_id}:{question.question_id[len(prefix) :]}"}
    )


def a2_questions(r: Sequence[Question], x: Sequence[Question]) -> list[Question]:
    """R plus every X isolation question typed `TAG_SET`; POSITION questions are not asked of A2."""
    return [*r, *(for_a2(q) for q in x if q.answer_type is AnswerType.VALVE_SET)]


def b_questions(r: Sequence[Question], x: Sequence[Question], a_id: str) -> list[Question]:
    """R plus all of X, relabelled to the B corpus id."""
    return [relabel_question(q, a_id, b_id_of(a_id)) for q in (*r, *x)]


def _jsonl(questions: Sequence[Question]) -> bytes:
    return "".join(q.model_dump_json() + "\n" for q in questions).encode("utf-8")


def _json(document: object) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


# ---- the baselines of POSITION_OF_VALVE -------------------------------------------------------


def load_priors(text: str) -> dict[NamedBy, FormPrior]:
    """The fitted priors back from `position_prior.json`."""
    document = json.loads(text)
    return {
        NamedBy(form): FormPrior(
            form=NamedBy(form),
            key_fields=tuple(entry["key_fields"]),
            majority=entry["majority"],
            table={tuple(row["key"]): row["position"] for row in entry["table"]},
        )
        for form, entry in document.items()
    }


def baseline_rows(
    x: Sequence[Question], pool: PlantPool, priors: Mapping[NamedBy, FormPrior], a_id: str
) -> list[dict[str, str]]:
    """One row per POSITION question: id, form, gold code, majority and text-prior predictions."""
    rows = []
    for question in x:
        if question.family is not QuestionFamily.POSITION_OF_VALVE:
            continue
        form = pool.flags[question.question_id].named_by
        if form is None:
            raise ValueError(f"expected a named_by flag on {question.question_id}, found none")
        prior = priors[form]
        key = pool.position_keys[question.question_id]
        rows.append(
            {
                "question_id": relabel_question(question, a_id, b_id_of(a_id)).question_id,
                "named_by": form.value,
                "gold": str(question.reference),
                "majority": prior.majority,
                "text_prior": prior.predict(key),
            }
        )
    return rows


# ---- writing ---------------------------------------------------------------------------------


def scope_report(
    pool: PlantPool, drop: DropSet, r: Sequence[Question], x: Sequence[Question]
) -> dict[str, object]:
    """Kept, refused and sampled counts per family, with X's flags (R8, R13)."""
    sampled = Counter(q.family.value for q in (*r, *x))
    kept_r = Counter(q.family.value for q in pool.r_pool)
    dropped = {
        f.value: ("pre-registered" if f in drop.pre_registered else "G0e")
        for f in sorted(drop.all, key=lambda f: f.value)
    }
    return {
        "dropped": dropped,
        "r_pool_per_family": dict(sorted(kept_r.items())),
        "sampled": dict(sorted(sampled.items())),
        "scope_x": [report.model_dump(mode="json") for report in pool.reports],
    }


def write_plant_files(
    a_id: str,
    pool: PlantPool,
    drop: DropSet,
    recipe: Recipe,
    questions_root: Path,
    priors: Mapping[NamedBy, FormPrior],
) -> dict[str, int]:
    """Write `questions/<A id>/` and `questions/<B id>/`; return the question counts.

    Raises:
        FileExistsError: a questions file of this plant exists (a draw is never redone).
    """
    r, r_splits = sample_r(pool, drop, recipe)
    x = sample_x(pool, drop, recipe)
    x_splits = {q.question_id: x_split(q) for q in x}
    b_id = b_id_of(a_id)
    a_dir, b_dir = questions_root / a_id, questions_root / b_id
    for folder in (a_dir, b_dir):
        if (folder / QUESTIONS_FILE).exists():
            raise FileExistsError(f"expected no {QUESTIONS_FILE} in {folder}, found one")
        folder.mkdir(parents=True, exist_ok=True)
    a_list, b_list = a2_questions(r, x), b_questions(r, x, a_id)
    splits = {**r_splits, **x_splits}
    (a_dir / QUESTIONS_FILE).write_bytes(_jsonl(a_list))
    (b_dir / QUESTIONS_FILE).write_bytes(_jsonl(b_list))
    (a_dir / SPLITS_FILE).write_bytes(_json(splits))
    b_splits = {f"{b_id}:{qid.split(':', 1)[1]}": split for qid, split in splits.items()}
    (b_dir / SPLITS_FILE).write_bytes(_json(b_splits))
    report = _json(scope_report(pool, drop, r, x))
    (a_dir / REPORT_FILE).write_bytes(report)
    (b_dir / REPORT_FILE).write_bytes(report)
    rows = baseline_rows(x, pool, priors, a_id)
    (b_dir / BASELINES_FILE).write_bytes(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode("utf-8")
    )
    return {"a2": len(a_list), "b": len(b_list), "r": len(r), "x": len(x)}
