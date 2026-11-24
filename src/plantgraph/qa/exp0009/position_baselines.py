"""What a POSITION_OF_VALVE question's text is worth without any retrieval (design `v2t-b` §10 R12).

A valve's position follows from its role (a vent is closed, a blocking valve is open), and the text
of a question already hints at the role: "a ball valve on the downstream side of a pump" is almost
always a pump vent. So a system can score well on POSITION questions by reading the *text* alone.
Two baselines say how well, so a right answer from system B is read against them:

- **majority:** always the most frequent position code of the training questions ("always NO");
- **text prior:** the most frequent code per **text key**, a key unseen in training falling back
  to the majority. Descriptor form: (valve class, side, class of `next_to`, fluid field of the
  line number). Tag form: (tag letters, valve class).

The protocol is the architect's: descriptor rows come from the forced-untagged plants, tag rows
from the forced-tagged ones; fit on seed 1 and score seeds 2-5 (the reproduction of §10.8 P3);
also leave-one-seed-out over seeds 1-5; the prior used in PREREG A is fitted on all of seeds 1-5.

    uv run python -m plantgraph.qa.exp0009.position_baselines --out-dir data/runs/exp0009/baselines
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.plan_models import OperatingPosition
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.exp0009.dev_plants import forced_config
from plantgraph.qa.questions.scope_x_models import NamedBy
from plantgraph.qa.questions.scope_x_position import next_to_node
from plantgraph.qa.v2tb.descriptor import Descriptor, PlantIndex, canonical_descriptor

DEV_SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5)
#: the plants' size in sheets (the dev plants of EXP-0009)
SHEETS = 100
#: the fields of a text key, named so the fitted file explains itself
KEY_FIELDS: dict[NamedBy, tuple[str, ...]] = {
    NamedBy.DESCRIPTOR: ("valve_class", "side", "next_to_class", "fluid_field"),
    NamedBy.TAG: ("tag_letters", "valve_class"),
}


class PositionRow(BaseModel):
    """One positioned valve as a baseline sees it: its text key and the answer."""

    model_config = ConfigDict(frozen=True)

    key: tuple[str, ...]
    position: str


class FormPrior(BaseModel):
    """The fitted baselines of one question form."""

    model_config = ConfigDict(frozen=True)

    form: NamedBy
    key_fields: tuple[str, ...]
    #: the most frequent code over all training rows
    majority: str
    #: text key -> its most frequent code
    table: dict[tuple[str, ...], str]

    def predict(self, key: tuple[str, ...]) -> str:
        """The prior's answer for a text key; the majority when the key was not seen."""
        return self.table.get(key, self.majority)


class Accuracy(BaseModel):
    """How often each baseline is right on a set of rows."""

    model_config = ConfigDict(frozen=True)

    rows: int
    prior_hits: int
    majority_hits: int
    unseen_keys: int

    @property
    def prior(self) -> float:
        """Share of rows the text prior gets right."""
        return self.prior_hits / self.rows if self.rows else 0.0

    @property
    def majority(self) -> float:
        """Share of rows the majority code gets right."""
        return self.majority_hits / self.rows if self.rows else 0.0


# ---- rows from a plant ---------------------------------------------------------------------------


def fluid_field(line_number: str) -> str:
    """The fluid part of a line number: `6"-P-1203-A1A` -> `P`.

    Raises:
        ValueError: the line number has no dash-separated second field.
    """
    fields = line_number.replace('"', "").split("-")
    if len(fields) < 2:
        raise ValueError(f'expected a line number like 6"-P-1203-A1A, found {line_number!r}')
    return fields[1]


def position_rows(
    plant: nx.DiGraph[str], positions: Mapping[str, OperatingPosition], form: NamedBy
) -> list[PositionRow]:
    """The baseline rows of one form: tagged valves for `TAG`, describable untagged for the rest."""
    index = PlantIndex(plant)
    rows: list[PositionRow] = []
    for node_id in positions:  # the plan's own order: it decides ties, so it must not be re-sorted
        tag = index.tag_of(node_id)
        if form is NamedBy.TAG and tag is not None:
            rows.append(PositionRow(key=_tag_key(index, node_id, tag), position=positions[node_id]))
        elif form is NamedBy.DESCRIPTOR and tag is None:
            descriptor = canonical_descriptor(index, node_id)
            if descriptor is not None:
                key = _descriptor_key(index, node_id, descriptor)
                rows.append(PositionRow(key=key, position=positions[node_id]))
    return rows


def _tag_key(index: PlantIndex, node_id: str, tag: str) -> tuple[str, ...]:
    return (tag.split("-")[0], index.node_class_of(node_id))


def _descriptor_key(index: PlantIndex, node_id: str, descriptor: Descriptor) -> tuple[str, ...]:
    neighbour = next_to_node(index, node_id, descriptor)
    return (
        index.node_class_of(node_id),
        descriptor.side.value,
        index.node_class_of(neighbour),
        fluid_field(descriptor.line_number),
    )


# ---- fitting and scoring (pure) -----------------------------------------------------------------


def fit_prior(form: NamedBy, rows: Sequence[PositionRow]) -> FormPrior:
    """The majority code and the most frequent code per text key.

    Raises:
        ValueError: `rows` is empty, so no majority exists.
    """
    if not rows:
        raise ValueError(f"expected rows to fit the {form.value} prior, found none")
    by_key: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_key[row.key][row.position] += 1
    majority = _most_frequent(Counter(row.position for row in rows))
    return FormPrior(
        form=form,
        key_fields=KEY_FIELDS[form],
        majority=majority,
        table={key: _most_frequent(counts) for key, counts in by_key.items()},
    )


def _most_frequent(counts: Counter[str]) -> str:
    """The commonest code; a tie goes to the code met first, in the plan's own valve order."""
    return counts.most_common(1)[0][0]


def score(prior: FormPrior, rows: Sequence[PositionRow]) -> Accuracy:
    """How often the prior and the majority code match the rows' positions."""
    return Accuracy(
        rows=len(rows),
        prior_hits=sum(prior.predict(row.key) == row.position for row in rows),
        majority_hits=sum(prior.majority == row.position for row in rows),
        unseen_keys=sum(row.key not in prior.table for row in rows),
    )


def fit_on_first_score_on_rest(
    rows_by_seed: Mapping[int, Sequence[PositionRow]], form: NamedBy
) -> dict[int, Accuracy]:
    """Fit on the lowest seed, score each other seed (the protocol of §10.8 P3)."""
    first, *rest = sorted(rows_by_seed)
    prior = fit_prior(form, rows_by_seed[first])
    return {seed: score(prior, rows_by_seed[seed]) for seed in rest}


def leave_one_seed_out(
    rows_by_seed: Mapping[int, Sequence[PositionRow]], form: NamedBy
) -> dict[int, Accuracy]:
    """For each seed, fit on all the other seeds and score that one."""
    result: dict[int, Accuracy] = {}
    for held_out in sorted(rows_by_seed):
        training = [r for seed, rows in rows_by_seed.items() if seed != held_out for r in rows]
        result[held_out] = score(fit_prior(form, training), rows_by_seed[held_out])
    return result


def fit_on_all(rows_by_seed: Mapping[int, Sequence[PositionRow]], form: NamedBy) -> FormPrior:
    """The prior that PREREG A pre-registers: every dev seed as training data."""
    return fit_prior(form, [row for rows in rows_by_seed.values() for row in rows])


# ---- the fitted file ----------------------------------------------------------------------------


def priors_as_json(priors: Mapping[NamedBy, FormPrior]) -> str:
    """Both priors as one sorted-key JSON document, so the same fit is always the same bytes."""
    document = {
        form.value: {
            "key_fields": list(prior.key_fields),
            "majority": prior.majority,
            "table": [
                {"key": list(key), "position": code} for key, code in sorted(prior.table.items())
            ],
        }
        for form, prior in priors.items()
    }
    return json.dumps(document, indent=1, sort_keys=True) + "\n"


def sha256_of(text: str) -> str:
    """The hex SHA-256 of the file text, as PREREG A will quote it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- the run -------------------------------------------------------------------------------------


def dev_rows(form: NamedBy) -> dict[int, list[PositionRow]]:
    """Generate one form's dev plants (forced untagged for descriptor rows) and read their rows."""
    untagged = form is NamedBy.DESCRIPTOR
    rows: dict[int, list[PositionRow]] = {}
    for seed in DEV_SEEDS:
        generated = generate_plant_v2(forced_config(SHEETS, seed, untagged=untagged))
        plant, _conversion = generated.graph()
        rows[seed] = position_rows(plant, positions_of(generated.plan.unit_plans), form)
    return rows


def _accuracy_table(results: Mapping[int, Accuracy]) -> dict[str, dict[str, float | int]]:
    return {
        str(seed): {
            "rows": a.rows,
            "prior": round(a.prior, 4),
            "majority": round(a.majority, 4),
            "unseen_keys": a.unseen_keys,
        }
        for seed, a in results.items()
    }


def main(argv: list[str] | None = None) -> None:
    """Fit both priors on dev seeds 1-5, print the accuracies and write the prior and its hash."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.position_baselines")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    rows = {form: dev_rows(form) for form in NamedBy}
    priors = {form: fit_on_all(rows[form], form) for form in NamedBy}
    text = priors_as_json(priors)
    report = {
        "prior_sha256": sha256_of(text),
        "seconds": round(time.perf_counter() - started, 1),
        "fit_seed_1_score_seeds_2_to_5": {
            form.value: _accuracy_table(fit_on_first_score_on_rest(rows[form], form))
            for form in NamedBy
        },
        "leave_one_seed_out": {
            form.value: _accuracy_table(leave_one_seed_out(rows[form], form)) for form in NamedBy
        },
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # bytes, not text: Windows text mode would write CRLF and the file would not match its hash
    (args.out_dir / "position_prior.json").write_bytes(text.encode("utf-8"))
    (args.out_dir / "position_baselines.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
